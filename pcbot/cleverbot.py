""" A port of https://github.com/folz/cleverbot.py to asynchronous python.

"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from builtins import str  # pylint: disable=redefined-builtin
from builtins import object  # pylint: disable=redefined-builtin

import collections
import hashlib
from requests.compat import urlencode
from future.backports.html import parser

import asyncio
import aiohttp

# Only use the instance method `unescape` of entity_parser. (I wish it was a
# static method or public function; it never uses `self` anyway)
entity_parser = parser.HTMLParser()


# noinspection PyArgumentList
class Cleverbot(object):
    """ Handles a conversation with Cleverbot. """
    HOST = "www.cleverbot.com"
    PROTOCOL = "http://"
    RESOURCE = "/webservicemin?uc=165&"
    API_URL = PROTOCOL + HOST + RESOURCE

    headers = {
        'User-Agent': 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0)',
        'Accept': 'text/html,application/xhtml+xml,'
                  'application/xml;q=0.9,*/*;q=0.8',
        'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
        'Accept-Language': 'en-us,en;q=0.8,en-us;q=0.5,en;q=0.3',
        'Cache-Control': 'no-cache',
        'Host': HOST,
        'Referer': PROTOCOL + HOST + '/',
        'Pragma': 'no-cache'
    }

    def __init__(self):
        """ The data that will get passed to Cleverbot's web API """
        self.data = collections.OrderedDict(
            (
                # must be the first pairs
                ('stimulus', ''),
                ('cb_settings_language', ''),
                ('cb_settings_scripting', 'no'),
                ('islearning', 1),  # Never modified
                ('icognoid', 'wsf'),  # Never modified
                ('icognocheck', ''),

                ('start', 'y'),  # Never modified
                ('sessionid', ''),
                ('vText8', ''),
                ('vText7', ''),
                ('vText6', ''),
                ('vText5', ''),
                ('vText4', ''),
                ('vText3', ''),
                ('vText2', ''),
                ('fno', 0),  # Never modified
                ('prevref', ''),
                ('emotionaloutput', ''),  # Never modified
                ('emotionalhistory', ''),  # Never modified
                ('asbotname', ''),  # Never modified
                ('ttsvoice', ''),  # Never modified
                ('typing', ''),  # Never modified
                ('lineref', ''),
                ('sub', 'Say'),  # Never modified
                ('cleanslate', False),  # Never modified
            )
        )

        # the log of our conversation with Cleverbot
        self.conversation = []

        # get the main page to get a cookie (see bug #13)
        self.session = aiohttp.ClientSession()
        asyncio.async(self.session.get(Cleverbot.PROTOCOL + Cleverbot.HOST))

    @asyncio.coroutine
    def ask(self, question):
        """Asks Cleverbot a question.

        Maintains message history.

        :param question: The question to ask
        :return Cleverbot's answer
        """

        # Set the current question
        self.data['stimulus'] = question

        # Connect to Cleverbot's API and remember the response
        resp = yield from self._send()
        text = yield from resp.text()

        # Add the current question to the conversation log
        self.conversation.append(question)

        parsed = self._parse(text)

        # Set data as appropriate
        if self.data['sessionid'] != '':
            self.data['sessionid'] = parsed['conversation_id']

        # Add Cleverbot's reply to the conversation log
        self.conversation.append(parsed['answer'])

        return parsed['answer']

    @asyncio.coroutine
    def _send(self):
        """ POST the user's question and all required information to the
        Cleverbot API """
        # Set data as appropriate
        if self.conversation:
            linecount = 1
            for line in reversed(self.conversation):
                linecount += 1
                self.data['vText' + str(linecount)] = line
                if linecount == 8:
                    break

        # Generate the token
        enc_data = urlencode(self.data)
        digest_txt = enc_data[9:35]
        token = hashlib.md5(digest_txt.encode('utf-8')).hexdigest()
        self.data['icognocheck'] = token

        # POST the data to Cleverbot's API and return
        resp = yield from self.session.post(Cleverbot.API_URL,
                                            data=self.data,
                                            headers=Cleverbot.headers)
        return resp

    @staticmethod
    def _parse(resp_text):
        """ Parses Cleverbot's response """
        resp_text = entity_parser.unescape(resp_text)

        parsed = [
            item.split('\r') for item in resp_text.split('\r\r\r\r\r\r')[:-1]
            ]

        if parsed[0][1] == 'DENIED':
            raise CleverbotAPIError()

        parsed_dict = {
            'answer': parsed[0][0],
            'conversation_id': parsed[0][1],
        }
        try:
            parsed_dict['unknown'] = parsed[1][-1]
        except IndexError:
            parsed_dict['unknown'] = None
        return parsed_dict


class CleverbotAPIError(Exception):
    """ Cleverbot returned an error (it probably recognized us as a bot) """
