#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A telegram bot that pulls information from CraftBeerPi

@author Guy Sheffer (GuySoft) <guysoft at gmail dot com>
"""
from telegram.ext import Updater
from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram.ext import MessageHandler, Filters, ConversationHandler, RegexHandler
from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import ReplyKeyboardMarkup
from emoji import emojize
import logging
from configparser import ConfigParser
from collections import OrderedDict
import os
import json
import glob
import sys
from urllib.request import urlopen, URLError
import time
import pytz
import subprocess

DIR = os.path.dirname(__file__)


def ini_to_dict(path):
    """ Read an ini path in to a dict

    :param path: Path to file
    :return: an OrderedDict of that path ini data
    """
    config = ConfigParser()
    config.read(path)
    return_value = OrderedDict()
    for section in reversed(config.sections()):
        return_value[section] = OrderedDict()
        section_tuples = config.items(section)
        for itemTurple in reversed(section_tuples):
            return_value[section][itemTurple[0]] = itemTurple[1]
    return return_value


def run_command(command, blocking=True):
    p = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if blocking:
        return [p.stdout.read().decode("utf-8"), p.stderr.read().decode("utf-8")]
    return


def get_timezones():
    return_value = {}
    for tz in pytz.common_timezones:
        c = tz.split("/")
        if len(c) > 1:
            if c[0] not in return_value.keys():
                return_value[c[0]] = []
            return_value[c[0]].append(c[1])

        for i in ["GMT"]:
            if i in return_value.keys():
                return_value.pop(i)

    return return_value


def tail(filepath):
    """
    @author Marco Sulla (marcosullaroma@gmail.com)
    @date May 31, 2016
    """

    try:
        filepath.is_file
        fp = str(filepath)
    except AttributeError:
        fp = filepath

    with open(fp, "rb") as f:
        size = os.stat(fp).st_size
        start_pos = 0 if size - 1 < 0 else size - 1

        if start_pos != 0:
            f.seek(start_pos)
            char = f.read(1)

            if char == b"\n":
                start_pos -= 1
                f.seek(start_pos)

            if start_pos == 0:
                f.seek(start_pos)
            else:
                char = ""

                for pos in range(start_pos, -1, -1):
                    f.seek(pos)

                    char = f.read(1)

                    if char == b"\n":
                        break

        return f.readline()


def get_temp(file_path):
    last_list = tail(file_path).decode("utf-8")
    return str(last_list.split(",")[1]) + "/" + str(last_list.split(",")[2])


class TelegramCallbackError(Exception):
    def __init__(self, message=""):
        self.message = message


def build_callback(data):
    return_value = json.dumps(data)
    if len(return_value) > 64:
        raise TelegramCallbackError("Callback data is larger tan 64 bytes")
    return return_value


def handle_cancel(update):
    query = update.message.text
    if query == "Close" or query == "/cancel":
        reply = "Perhaps another time"
        update.message.reply_text(reply)
        return reply
    return None


class Bot:
    def __init__(self, token):
        self.selected_continent = ""
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher
        start_handler = CommandHandler('start', self.start)
        self.dispatcher.add_handler(start_handler)

        self.TIMEZONE_CONTINENT, self.TIMEZONE_TIME = range(2)

        # Add conversation handler with the states TIMEZONE_CONTINENT, TIMEZONE_TIME
        set_timezone_handler = ConversationHandler(
            entry_points=[CommandHandler('timezone', self.set_timezone)],
            states={
                self.TIMEZONE_CONTINENT: [
                    RegexHandler('^(' + "|".join(get_timezones().keys()) + '|/cancel)$', self.timezone_continent)],

                self.TIMEZONE_TIME: [RegexHandler('^(.*)$', self.timezone_time)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.dispatcher.add_handler(set_timezone_handler)

        help_handler = CommandHandler('help', self.help)
        self.dispatcher.add_handler(help_handler)

        time_handler = CommandHandler('time', self.time)
        self.dispatcher.add_handler(time_handler)

        status_handler = CommandHandler('status', self.status)
        self.dispatcher.add_handler(status_handler)

        self.dispatcher.add_error_handler(self.error_callback)

        return

    def start(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id,
                         text="I'm a bot to do stuff with CraftBeerPi, please type /help for info")
        return

    def set_timezone(self, bot, update):
        keyboard = []

        for continent in sorted(get_timezones().keys()):
            keyboard.append([InlineKeyboardButton(continent)])

        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        update.message.reply_text('Please select a continent, or /cancel to cancel:', reply_markup=reply_markup)
        return self.TIMEZONE_CONTINENT

    def timezone_continent(self, bot, update):
        reply = handle_cancel(update)
        if reply is None:
            keyboard = []
            self.selected_continent = update.message.text
            for continent in sorted(get_timezones()[self.selected_continent]):
                keyboard.append([InlineKeyboardButton(continent)])
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            update.message.reply_text('Please select a timezone, or /cancel to cancel:', reply_markup=reply_markup)

            return self.TIMEZONE_TIME
        return ConversationHandler.END

    def timezone_time(self, bot, update):
        reply = handle_cancel(update)
        if reply is None:
            timezone = self.selected_continent + "/" + update.message.text

            timezone_script = os.path.join(DIR, "set_timezone.sh")

            if os.path.isfile(os.path.join("/usr/share/zoneinfo/", timezone)):
                print(run_command(["sudo", timezone_script, timezone]))
                update.message.reply_text(emojize(":clock4: ", use_aliases=True) + 'Timezone set set to: ' + timezone)
            else:
                update.message.reply_text(
                    emojize(":no_entry_sign: ", use_aliases=True) + 'Timezone file does not exist: ' + timezone)

            return ConversationHandler.END
        return ConversationHandler.END

    def cancel(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="Perhaps another time")
        return

    def error_callback(self, bot, update, error):
        try:
            raise error
        except Unauthorized as e:
            # remove update.message.chat_id from conversation list
            pass
        except BadRequest:
            # handle malformed requests - read more below!
            pass
        except TimedOut:
            # handle slow connection problems
            pass
        except NetworkError:
            # handle other connection problems
            pass
        except ChatMigrated as e:
            # the chat_id of a group has changed, use e.new_chat_id instead
            pass
        except TelegramError:
            # handle all other telegram related errors
            pass
        return

    def help(self, bot, update):
        icon = emojize(":information_source: ", use_aliases=True)
        text = icon + " The following commands are available:\n"

        commands = [["/status", "Check temps status"],
                    ["/timezone", "Set the timezone (only works if sudo requires no password)"],
                    ["/time", "Print time and timezone on device"],
                    ["/help", "Get this message"]
                    ]

        for command in commands:
            text += command[0] + " " + command[1] + "\n"

        bot.send_message(chat_id=update.message.chat_id, text=text)

    def time(self, bot, update):
        reply, _ = run_command(["date"])
        bot.send_message(chat_id=update.message.chat_id, text=reply)
        return

    def status(self, bot, update):
        log_dir = os.path.expanduser(os.path.join("~", "CraftBeerPi", "log"))
        reply = "Temps status :\n"
        for i in glob.glob(os.path.join(log_dir, "*.templog")):
            reply += os.path.basename(i) + ": " + get_temp(i) + "\n"

        bot.send_message(chat_id=update.message.chat_id, text=reply)
        return

    def run(self):
        self.updater.start_polling()
        return


def check_connectivity(reference):
    try:
        urlopen(reference, timeout=1)
        return True
    except URLError:
        return False


def wait_for_internet():
    while not check_connectivity("https://api.telegram.org"):
        print("Waiting for internet")
        time.sleep(1)


if __name__ == "__main__":
    config_file_path = os.path.join(DIR, "config.ini")
    settings = ini_to_dict(config_file_path)
    if not config_file_path:
        print("Error, no config file")
        sys.exit(1)
    if ("main" not in settings) or ("token" not in settings["main"]):
        print("Error, no token in config file")

    wait_for_internet()

    a = Bot(settings["main"]["token"])
    a.run()
    print("Bot Started")
