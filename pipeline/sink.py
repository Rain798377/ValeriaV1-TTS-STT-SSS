"""
VoiceSink — uses py-cord's built-in WaveSink to capture audio.

py-cord's sink API works differently from what we assumed:
- vc.start_recording(sink, callback, channel) starts recording
- vc.stop_recording() stops it and fires the callback with sink.audio_data
- sink.audio_data = {user_id: AudioData} where AudioData has a .file (BytesIO WAV)

So instead of streaming VAD, we do timed chunks:
- Record for N seconds, stop, process, restart
- Simple and reliable with py-cord's actual API
"""

import discord

class VoiceSink:
    """Wrapper around py-cord's WaveSink for our pipeline."""

    @staticmethod
    def create():
        return discord.sinks.WaveSink()