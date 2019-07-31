# The MIT License(MIT)
# Copyright(c) 2019 Tiago Santos
# Copyright(c) 2016 Joseph Milazzo
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files(the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# This file is to find and convert all avi/mkv/etc to mp4/m4v
#
# Requirements:
# Python 3
# python-psutil
# python-mediainfo
# ffmpeg
#
# Usage:
#
# Edit settings below
# Run with "python3 media_convert_2.py"

# This is based off of the media-convert script created by Joseph Milazzo
# https://bitbucket.org/majora2007/media-convert/src/master/

from collections import defaultdict
import os
import logging
from pymediainfo import MediaInfo
import subprocess
import signal
import psutil
import time
import sys


#######################################################################
#                       Variables

# EXT should be either mp4 or m4v. m4v should be chosen if you have multi-track audio and Apple TV users
global EXT
EXT = 'mp4'

# temporary enconding file
temp_file = '/home/plex/temp.' + EXT

# A list of directories to scan
watched_folders = ['/home/plex/Concerts/', '/home/plex/Series']
exclude = []

# Conditions for video recoding
MAX_BITRATE = 7000000
MAX_HEIGHT = 1080
VIDEO_CODEC = "AVC"
# Recode all videos ending with these extensions
valid_extensions = ['rmvb', 'mkv', 'avi']

# Conditions for audio recoding
MAX_CHANNELS = 2
AUDIO_CODEC = "AAC"

# FFMPEG parameters
ffmpeg_base_cmd = "ffmpeg -loglevel error -hide_banner -hwaccel auto -i "
ffmpeg_video_encode = " -c:v libx264 -preset faster -crf 23 -vf \"scale=-1:\'min(1080,ih)\'\" "
ffmpeg_audio_encode = " -c:a aac -ac 2 -b:a 192k "

# Flag to denote whether to delete source files after successfull encode
DELETE = True

# Flag to denote whether to just run MediaInfo on files
JUST_CHECK = False

# Paths to all valid files
paths = []
# List of conversions
commands = []

#######################################################################


def setup_logger(dir, filename, debug_lvl):
    log_file = filename
    log_directory = os.path.abspath(dir)

    if not os.path.exists(log_directory):
        os.mkdir(log_directory)

    log_filePath = os.path.join(log_directory, log_file)

    if not os.path.isfile(log_filePath):
        with open(log_filePath, "w") as emptylog_file:
            emptylog_file.write('')

    logging.basicConfig(filename=log_filePath, level=debug_lvl,
                        format='%(asctime)s %(message)s')


def needs_convert(file):
    for extension in valid_extensions:
        if file.endswith(extension):
            return True
    if file.endswith(EXT):
        media_info = MediaInfo.parse(file)
        if MediaInfo.can_parse():
            for track in media_info.tracks:
                if track.track_type == 'Video':
                    if not track.format.startswith(VIDEO_CODEC) or track.bit_rate > MAX_BITRATE or track.height > MAX_HEIGHT:
                        return True
                elif track.track_type == 'Audio':
                    if track.channel_s > MAX_CHANNELS or not track.format.startswith(AUDIO_CODEC):
                        return True
    return False


def normalize_path(path):
    return path.replace('\\', '/')


def to_mp4_naming(filename):
    parts = filename.split('.')
    parts[len(parts)-1] = EXT
    output_path = '.'.join(parts)
    return output_path


def delete(path):
    logger = logging.getLogger(__name__)
    logger.info('Deleting ' + path)
    try:
        os.remove(path)
    except OSError:
        logger.exception(
            'There was an issue deleting ' + str(media.tracks[0].complete_name))


def move(file_from, file_to):
    logger = logging.getLogger(__name__)
    logger.info('Moving ' + file_from + ' to ' + file_to)
    try:
        os.rename(file_from, file_to)
    except OSError:
        logger.exception('There was an issue moving ' +
                         file_from + ' to ' + file_to)


def signal_handler(signum, frame):
    pass


if __name__ == '__main__':
    setup_logger('.', 'media-convert.log', logging.DEBUG)
    logger = logging.getLogger(__name__)
    # Register signals, such as CTRL + C
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logger.info("######### Script Executed at " +
                time.asctime(time.localtime(time.time())))

    for base_path in watched_folders:
        base_path = normalize_path(base_path)
        print('Searching for files in ' + base_path)
        logger.info('Searching for files in ' + base_path)
        t0 = time.time()
        for root, dirs, files in os.walk(base_path, topdown=True):
            dirs[:] = [d for d in dirs if d not in exclude]
            for file in files:
                if needs_convert(os.path.join(root, file)):
                    path = os.path.join(root, file)
                    paths.append(normalize_path(path))
        t1 = time.time()
        print('[Directory Scan] Execution took %s ms' % str(t1-t0))
    logger.info('=====Scan Complete=====')
    logger.info('Total files scanned: ' + str(len(paths)))
    print('Total files scanned: ' + str(len(paths)))

    print('Calculating conversions...')
    t0 = time.time()
    count = 0.0
    for path in paths:
        count += 1.0
        cur_file = normalize_path(path)
        logger.debug('Calculating MediaInfo for: ' + cur_file)
        ffmpeg_cmd = ffmpeg_base_cmd + "\"" + cur_file + "\""
        video_cmd = ' -c:v copy '
        audio_cmd = ' -c:a copy '
        media_info = MediaInfo.parse(normalize_path(path))
        if MediaInfo.can_parse():
            for track in media_info.tracks:
                if track.track_type == 'Video':
                    if not track.format.startswith(VIDEO_CODEC) or track.bit_rate > MAX_BITRATE or track.height > MAX_HEIGHT:
                        video_cmd = ffmpeg_video_encode
                elif track.track_type == 'Audio':
                    if track.channel_s > MAX_CHANNELS or not track.format.startswith(AUDIO_CODEC):
                        audio_cmd = ffmpeg_audio_encode
        ffmpeg_cmd = ffmpeg_cmd + video_cmd + audio_cmd + "\"" + temp_file + "\""

        if JUST_CHECK:
            commands.append(ffmpeg_cmd)
        else:
            if os.path.isfile(temp_file):
                delete(temp_file)
            print('Encoding ' + cur_file)
            p = subprocess.Popen(
                ffmpeg_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in p.stdout.readlines():
                logger.debug(line)
            retval = p.wait()
            logger.debug('Convert returned: ' + str(retval))
            print('Convert finished')
            if retval == 0:
                print('File processed successfully')
                if DELETE:
                    delete(cur_file)
                    move(temp_file, to_mp4_naming(cur_file))
                else:
                    if cur_file == to_mp4_naming(cur_file):
                        cur_file = cur_file + ".new.mp4"
                    move(temp_file, to_mp4_naming(cur_file))

    t1 = time.time()
    print('\n\n')
    print('[Media Check] Execution took %s ms' % str(t1-t0))

    if JUST_CHECK:
        for cmd in commands:
            print(cmd)