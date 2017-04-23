""" This plugin is designed for various image utility commands.

Commands:
    resize """
import re
from io import BytesIO

from PIL import Image, ImageSequence, ImageOps
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
mention_regex = re.compile(r"<@!?(?P<id>\d+)>")
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

    def clean_format(self, real_convert=True):
        """ Return working options of JPG images. """
        if self.extension.lower() == "jpeg":
            self.extension = "jpg"
        if self.format.lower() == "jpg":
            self.format = "JPEG"

        if self.format == "JPEG" and real_convert:
            self.to_rgb()

    def set_extension(self, ext: str, real_jpg=True):
        """ Change the extension of an image. """
        self.extension = self.format = ext
        self.clean_format(real_convert=real_jpg)

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

    def to_rgb(self):
        """ Convert to RGB using solution from http://stackoverflow.com/questions/9166400/ """
        if not self.object.mode == "RGBA":
            return

        self.object.load()
        background = Image.new("RGB", self.object.size, (0, 0, 0))
        background.paste(self.object, mask=self.object.split()[3])
        self.object = background


@plugins.argument("{open}url/@user" + ("" if url_only else "/emoji") + "{suffix}{close}", pass_message=True)
async def image(message: discord.Message, url_or_emoji: str):
    """ Parse a url or emoji and return an ImageArg object. """
    # Remove <> if the link looks like a URL, to allow for embed escaped links.
    if "http://" in url_or_emoji or "https://" in url_or_emoji:
        url_or_emoji = url_or_emoji.strip("<>")

    try:  # Check if the given string is a url and save the headers for later
        headers = await utils.retrieve_headers(url_or_emoji)
    except ValueError:  # Not a valid url, let's see if it's a mention
        match = mention_regex.match(url_or_emoji)
        if match:
            member = message.server.get_member(match.group("id"))
            avatar_headers = await utils.retrieve_headers(member.avatar_url)
            assert not avatar_headers["CONTENT-TYPE"].endswith("gif"), "**GIF avatars are currently unsupported.**"

            image_bytes = await utils.download_file(member.avatar_url.replace(".webp", ".png"), bytesio=True)
            image_object = Image.open(image_bytes)
            return ImageArg(image_object, format="PNG")

        # Nope, not a mention. If we support emoji, we can progress further
        assert not url_only, "`{}` **is not a valid URL or user mention.**".format(url_or_emoji)

        # There was no image to get, so let's see if it's an emoji
        char = "-".join(hex(ord(c))[2:] for c in url_or_emoji)  # Convert to a hex string
        image_object = get_emoji(char, size=256)
        if image_object:
            return ImageArg(image_object, format="PNG")

        # Not an emoji, perhaps it's an emote
        match = emote_regex.match(url_or_emoji)
        if match:
            image_object = await get_emote(match.group("id"), message.server)
            if image_object:
                return ImageArg(image_object, format="PNG")

        # Alright, we're out of ideas
        raise AssertionError("`{}` **is neither a URL, a mention nor an emoji.**".format(url_or_emoji))

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
    image_bytes = await utils.download_file(url_or_emoji, bytesio=True)
    image_object = Image.open(image_bytes)
    return ImageArg(image_object, format=image_format)


@plugins.argument("({open}width{close}x{open}height{close} or *{open}scale{close})")
def parse_resolution(res: str):
    """ Parse a resolution string.

    If the y value is zero, the x value is the number to scale the image with. """
    # Check what type of input we're parsing
    if res.count("x") == 1:
        # Try parsing the numbers in the resolution
        x, y = res.split("x")
        try:
            x = int(x)
            y = int(y)
        except ValueError:
            raise AssertionError("**Width or height are not integers.**")

        # Assign a maximum and minimum size
        assert 1 <= x <= 3000 and 1 <= y <= 3000, "**Width and height must be between 1 and 3000.**"
        return x, y
    elif res.startswith("*"):
        try:
            scale = float(res[1:])
        except ValueError:
            raise AssertionError("**Characters following \* must be a number, not `{}`**".format(res[1:]))

        # Make sure the scale isn't less than 0. Whatever uses this argument will have to manually check for max size
        assert scale > 0, "**Scale must be greater than 0.**"
        return scale, 0
    else:
        return None


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
    or `*<scale>` with an optional extension. """
    if extension:
        image_arg.set_extension(extension)

    # Generate a new image based on the scale
    if resolution[1] == 0:
        w, h = image_arg.object.size
        scale = resolution[0]
        assert w * scale < 3000 and h * scale < 3000, "**The result image must be less than 3000 pixels in each axis.**"
        resolution = (int(w * scale), int(h * scale))

    # Resize and upload the image
    image_arg.modify(Image.Image.resize, resolution, Image.NEAREST if "-nearest" in options else Image.ANTIALIAS)
    await send_image(message, image_arg)


@plugins.command(pos_check=lambda s: s.startswith("-"), aliases="tilt")
async def rotate(message: discord.Message, image_arg: image, degrees: int, *options, extension: str.lower=None):
    """ Rotate an image clockwise using the given degrees. """
    if extension:
        image_arg.set_extension(extension)

    # Rotate and upload the image
    image_arg.modify(Image.Image.rotate, -degrees, Image.NEAREST if "-nearest" in options else Image.BICUBIC,
                     expand=True)
    await send_image(message, image_arg)


@plugins.command(name="convertimage")
async def convert(message: discord.Message, image_arg: image, extension: str.lower):
    """ Convert an image to a specified extension. """
    image_arg.set_extension(extension)
    await send_image(message, image_arg)


@plugins.command(aliases="jpg")
async def jpeg(message: discord.Message, image_arg: image, *effect: utils.choice("small", "meme"),
               quality: utils.int_range(f=0, t=100)=5):
    """ Give an image some proper jpeg artifacting.

    Valid effects are: `small` """
    assert not image_arg.gif, "**JPEG saving only works on images.**"
    image_arg.set_extension("jpg", real_jpg=False if "meme" in effect else True)

    if effect:
        if "small" in effect:
            w, h = image_arg.object.size
            image_arg.modify(Image.Image.resize, (w // 3, h // 3))

    await send_image(message, image_arg, quality=quality)


@plugins.command()
async def invert(message: discord.Message, image_arg: image):
    """ Invert the colors of an image. """
    image_arg.set_extension("jpg")

    # This function only works in images because of PIL limitations
    assert not image_arg.gif, "**This command does not support GIF files.**"

    # Invert the colors and upload the image
    image_arg.modify(ImageOps.invert)
    await send_image(message, image_arg, quality=100)


@plugins.command()
async def flip(message: discord.Message, image_arg: image, extension: str.lower=None):
    """ Flip an image in the y-axis. """
    if extension:
        image_arg.set_extension(extension)

    # Flip the image
    image_arg.modify(Image.Image.transpose, Image.FLIP_TOP_BOTTOM)
    try:
        await send_image(message, image_arg)
    except IOError:
        await client.say(message, "**The image format is not supported (must be L or RGB)**")


@plugins.command()
async def mirror(message: discord.Message, image_arg: image, extension: str.lower=None):
    """ Mirror an image along the x-axis. """
    if extension:
        image_arg.set_extension(extension)

    # Mirror the image
    image_arg.modify(Image.Image.transpose, Image.FLIP_LEFT_RIGHT)
    await send_image(message, image_arg)
