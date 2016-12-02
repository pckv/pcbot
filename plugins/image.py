""" This plugin is designed for various image utility commands.

Commands:
    resize """
import re
from io import BytesIO

from PIL import Image, ImageSequence
import discord

import plugins
from pcbot import utils

url_only, gif_support = False, True

# See if we can convert emoji using the emoji.py plugin
try:
    from .emoji import get_emote, get_emoji, emote_regex
except:
    url_only = True

# See if we can create gifs using imageio
try:
    import imageio
except:
    gif_support = False


client = plugins.client  # type: discord.Client

extension_regex = re.compile(r"image/(?P<ext>\w+)(?:\s|$)")
max_bytes = 4096 ** 2  # 4 MB
max_gif_bytes = 1024 * 128  # 128kB


class ImageArg:
    def __init__(self, image_object: Image.Image, format: str):
        self.object = image_object
        self.format = format
        self.extension = format.lower()
        self.clean_format()

        # Figure out if this is a gif by looking for the duration argument. Might only work for gifs
        self.gif = bool(self.object.info.get("duration"))
        self.gif_bytes = None   # For easier upload of gifs, store the bytes in memory


    def clean_format(self):
        """ Return working options of JPG images. """
        if self.extension.lower() == "jpeg":
            self.extension = "jpg"
        if self.format.lower() == "jpg":
            self.format = "JPEG"

    def set_extension(self, ext: str):
        self.extension = self.format = ext
        self.clean_format()

    def modify(self, function, *args, **kwargs):
        """ Modify the image object using the given Image function.
        This function supplies sequence support. """
        if not gif_support or not self.gif:
            self.object = function(self.object, *args, **kwargs)
        else:
            frames = []
            duration = self.object.info.get("duration") / 1000
            for frame in ImageSequence.Iterator(self.object):
                frame_bytes = utils.convert_image_object(function(frame, *args, **kwargs))
                frames.append(imageio.imread(frame_bytes, format="PNG"))

            # Save the image as bytes and recreate the image object
            image_bytes = imageio.mimwrite(imageio.RETURN_BYTES, frames, format=self.format, duration=duration)
            self.object = Image.open(BytesIO(image_bytes))
            self.gif_bytes = image_bytes


@plugins.argument("{open}url" + ("" if url_only else " or emoji") + "{suffix}{close}", pass_message=True)
async def image(message: discord.Message, url_or_emoji: str):
    """ Parse a url or emoji and return an ImageArg object. """
    # Remove <> if the link looks like a URL, to allow for embed escaped links.
    if "http://" in url_or_emoji or "https://" in url_or_emoji:
        url_or_emoji = url_or_emoji.strip("<>")

    try:  # Check if the given string is a url and save the headers for later
        headers = await utils.retrieve_headers(url_or_emoji)
    except ValueError:  # Not a valid url, figure out if we support emoji
        assert not url_only, "`{}` **is not a valid URL.**".format(url_or_emoji)

        # There was no image to get, so let's see if it's an emoji
        char = "-".join(hex(ord(c))[2:] for c in url_or_emoji)  # Convert to a hex string
        image_object = get_emoji(char, size=256)
        if image_object:
            return ImageArg(image_object, format="PNG")

        # Not an emoji, so perhaps it's an emote
        match = emote_regex.match(url_or_emoji)
        if match:
            image_object = await get_emote(match.group("id"), message)
            if image_object:
                return ImageArg(image_object, format="PNG")

        # Alright, we're out of ideas
        raise AssertionError("`{}` **is neither a URL or an emoji.**".format(url_or_emoji))

    # The URL was valid so let's make sure it's an image
    match = extension_regex.search(headers["CONTENT-TYPE"])
    assert match, "**The given URL is not an image.**"
    image_format = match.group("ext")

    # Make sure the image is not too big
    gif = image_format.lower() == "gif"
    if "CONTENT-LENGTH" in headers:
        size = headers["CONTENT-LENGTH"]
        max_size = max_gif_bytes if gif else max_bytes
        assert int(size) <= max_size, \
            "**This image exceeds the maximum size of `{}kB` for this format.**".format(max_size // 1024)
    elif gif:  # If there is no information on the size of the file, we'll refuse if the image is a gif
        raise AssertionError("**The size of this GIF is unknown and was therefore rejected.**")

    # Download the image and create the object
    image_bytes = await utils.download_file(url_or_emoji)
    image_object = Image.open(BytesIO(image_bytes))
    return ImageArg(image_object, format=image_format)


@plugins.argument("{open}width{suffix}{close}x{open}height{suffix}{close}")
def parse_resolution(res: str):
    """ Parse a resolution string. """
    # Show help when the format is incorrect
    if not res.count("x") == 1:
        return None

    # Try parsing the numbers in the resolution
    x, y = res.split("x")
    try:
        x = int(x)
        y = int(y)
    except ValueError:
        return None

    # Assign a maximum and minimum size
    if not (1 <= x <= 3000 and 1 <= y <= 3000):
        raise AssertionError("**Width and height must be between 1 and 3000.**")

    return x, y


def clean_format(image_format: str, extension: str):
    """ Return working options of JPG images. """
    if extension.lower() == "jpeg":
        extension = "jpg"
    if image_format.lower() == "jpg":
        image_format = "JPEG"

    return image_format, extension


async def send_image(message: discord.Message, image_arg: ImageArg, **params):
    """ Send an image. """
    try:
        if image_arg.gif and gif_support:
            image_fp = BytesIO(image_arg.gif_bytes)
        else:
            image_fp = utils.convert_image_object(image_arg.object, image_arg.format, **params)
    except KeyError as e:
        await client.send_message(message.channel, "Image format `{}` is unsupported.".format(e))
    else:
        await client.send_file(message.channel, image_fp,
                               filename="{}.{}".format(message.author.display_name, image_arg.extension))


@plugins.command(pos_check=lambda s: s.startswith("-"))
async def resize(message: discord.Message, image_arg: image, resolution: parse_resolution, *options,
                 extension: str.lower=None):
    """ Resize an image with the given resolution formatted as `<width>x<height>`
    with an optional extension. """
    if extension:
        image_arg.set_extension(extension)

    # Resize and upload the image
    image_arg.modify(Image.Image.resize, resolution, Image.NEAREST if "-nearest" in options else Image.ANTIALIAS)
    await send_image(message, image_arg)


@plugins.command(pos_check=lambda s: s.startswith("-"), aliases="tilt")
async def rotate(message: discord.Message, image_arg: image, degrees: int, *options, extension: str=None):
    """ Rotate an image clockwise using the given degrees. """
    # Set the image upload format, extension and filename
    if extension:
        image_arg.set_extension(extension)

    # Rotate and upload the image
    image_arg.modify(Image.Image.rotate, -degrees, Image.NEAREST if "-nearest" in options else Image.BICUBIC,
                     expand=True)
    await send_image(message, image_arg)


@plugins.command()
async def convert(message: discord.Message, image_arg: image, extension: str.lower):
    """ Convert an image to a specified extension. """
    image_arg.set_extension(extension)
    await send_image(message, image_arg)


@plugins.command(aliases="jpg")
async def jpeg(message: discord.Message, image_arg: image, quality: utils.int_range(f=0, t=100)=5):
    """ Give an image some proper jpeg artifacting. """
    assert not image_arg.gif, "**JPEG saving only works on images.**"
    image_arg.set_extension("jpg")
    await send_image(message, image_arg, quality=quality)
