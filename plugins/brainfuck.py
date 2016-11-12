""" Plugin for compiling and executing brainfuck code. """

from collections import namedtuple

import discord

import plugins
from pcbot import Annotate
client = plugins.client  # type: discord.Client


Loop = namedtuple("Loop", "start end")


class TooManyIterations(Exception):
    pass


class Pointer:
    cells = 2 ** 15
    cell_size = 2 ** 8 - 1

    def __init__(self):
        self.array = [0] * self.cells
        self.cursor = 0

    @property
    def value(self):
        return self.array[self.cursor]

    @value.setter
    def value(self, value):
        self.array[self.cursor] = value

    def add(self):
        self.value += 1
        if self.value > self.cell_size:
            self.value = 0

    def sub(self):
        self.value -= 1
        if self.value < 0:
            self.value = self.cell_size

    def right(self):
        self.cursor += 1
        if self.cursor < 0:
            self.cursor = self.cells

    def left(self):
        self.cursor -= 1
        if self.cursor > self.cells:
            self.cursor = 0


def find_loop_end(code: str, start: int):
    nest = 1
    for i, c in enumerate(code):
        if c == "[":
            nest += 1
        elif c == "]":
            nest -= 1

        if nest == 0:
            return start + i

    raise SyntaxError("{}: Loop never ends!".format(start))


def run_brainfuck(code: str, for_input: str=""):
    pointer = Pointer()
    input_pointer = Pointer()
    input_pointer.array[:len(for_input)] = list(ord(c) for c in for_input)
    loops = []
    max_iterations = 2 ** 16

    i, iterations = 0, 0
    output = ""
    while True:
        char = code[i]

        if char == "+":
            pointer.add()
        elif char == "-":
            pointer.sub()
        elif char == ">":
            pointer.right()
        elif char == "<":
            pointer.left()
        elif char == ".":
            output += chr(pointer.value)
        elif char == ",":
            pointer.value = input_pointer.value
            input_pointer.right()
        elif char == "[":
            end = find_loop_end(code[i + 1:], i)
            loops.append(Loop(start=i, end=end))
            if pointer.value == 0:
                i = end
        elif char == "]":
            if not pointer.value == 0:
                i = loops[-1].start
            else:
                del loops[-1]

        i += 1
        if i >= len(code):
            return output or "Pointer value: {}".format(pointer.value)

        iterations += 1
        if iterations >= max_iterations:
            raise TooManyIterations("Program exceeded maximum number of iterations ({})".format(max_iterations))


@plugins.command(aliases="bf")
async def brainfuck(message: discord.Message, code: Annotate.Code):
    program_input = ""
    if "," in code:
        await client.say(message, "**Input required, please type:**")
        reply = await client.wait_for_message(timeout=30, author=message.author, channel=message.channel)
        assert reply, "**You failed to reply.**"

        program_input = reply.clean_content

    try:
        output = run_brainfuck(code, program_input)
    except Exception as e:
        await client.say(message, "```\n{}: {}```".format(type(e).__name__, str(e)))
    else:
        assert len(output) <= 2000, "**The output was too long.**"
        await client.say(message, "```\n{}```".format(output))
