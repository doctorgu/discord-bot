import discord
# 1065070237583683675
# MTEzMDg1NjUyNDQyODg2OTc1Ng.GepNek.wvnfHIE7rfRsnMsRd20zsyE57iKYQKrm73ryVk


class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)

    async def on_message(self, message):
        print(message)
        # don't respond to ourselves
        if message.author == self.user:
            return

        if message.content == 'ping':
            await message.channel.send('pong')


intents = discord.Intents.default()
intents.message_content = True
client = MyClient(intents=intents)
client.run(
    'MTEzMDg1NjUyNDQyODg2OTc1Ng.GepNek.wvnfHIE7rfRsnMsRd20zsyE57iKYQKrm73ryVk')
