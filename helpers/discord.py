import os
import discord
import logging

logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


# Function to send a message to a specific channel
async def send_message(message):
    # Retrieve the Discord bot token from environment variables
    TOKEN = os.environ.get('DISCORD_TOKEN')
    #logger.info('The TOKEN is')
    #logger.info(TOKEN)
    
    # Retrieve the Discord channel ID from environment variables
    CHANNEL = os.environ.get('DISCORD_CHANNEL')
    #logger.info('The Channel is')
    #logger.info(CHANNEL)

    # Define intents
    intents = discord.Intents.default()

    # Authenticate with the bot token
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        channel = client.get_channel(int(CHANNEL))
        await channel.send(message)

    await client.start(TOKEN)
    
def init_send_message(message):
    
    from tasks import send_message_async
    try:
        result = send_message_async.delay(message)
        logger.info(f"Celery send_message_async task called successfully! Task ID: {result.id}")
    except Exception as e:
        logger.error("This is an error message from helpers/discord.py while trying to send_message_async")
        logger.error(e)    