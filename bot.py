import discord
from discord.ext import commands
import os
from discord_slash import SlashCommand, SlashContext
from dotenv import load_dotenv
import youtube_dl
import asyncio

load_dotenv()

TOKEN = os.getenv('discord_token')
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix=".", description='一支簡單的機器人', intents=intents)
slash = SlashCommand(bot, sync_commands=True)

guild_ids = [863362246121619486]

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
waiting_queue = []

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download= not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepared_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class MusicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def join(self, ctx):
        channel_to_add = None
        for channel in bot.get_all_channels():
            
            if channel.type == discord.ChannelType.voice and ctx.author in channel.members:
                # print(channel.type, type(ctx.author), type(channel.members[0]))
                channel_to_add = channel
                break
        if not channel_to_add:
            await ctx.send(f'你沒有加入語音頻道喔')
            return
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel_to_add)
        await channel_to_add.connect()

    @commands.command()
    async def play(self, ctx, *, url):
        def next_song():
            if len(waiting_queue) > 0:
                player = waiting_queue.pop(0)
                ctx.voice_client.play(player, after=lambda e: error(e))
                coro = ctx.send(f'Playing: {player.title}')
                fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                try:
                    fut.result()
                except:
                    pass

        def error(e):
            print(f'Error: {e}') if e else None
            next_song()
        
        if not ctx.voice_client.is_playing():
            async with ctx.typing():
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                ctx.voice_client.play(player, after=lambda e: error(e))
            await ctx.send(f'Playing: {player.title}')
        else:
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            waiting_queue.append(player)
            await ctx.send(f'Queued: {player.title}')
    

    @commands.command()
    async def volume(self, ctx, *, volume: int):
        if ctx.voice_client is None:
                return await ctx.send("Not connected to a voice channel.")
        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.command()
    async def leave(self, ctx):
        """Stops and disconnects the bot from voice"""
        await ctx.voice_client.disconnect()

    @commands.command()
    async def stop(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send(f'停止音樂')

    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send(f'暫停音樂')

    @commands.command()
    async def resume(self, ctx):
        if ctx.voice_client and not ctx.voice_client.is_playing():
            ctx.voice_client.resume()
            await ctx.send(f'繼續播放音樂')

    @commands.command()
    async def help(self, ctx):
        help_text = "本機器人指令皆以.為開頭\n" + \
            ".join\t\t邀請加入發送者所在的頻道" +\
            ".play URL\t\t加入播放清單，目前支援youtube\n" + \
            "."

        await ctx.send(help_text)

@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))

bot.add_cog(MusicBot(bot))
bot.run(TOKEN)