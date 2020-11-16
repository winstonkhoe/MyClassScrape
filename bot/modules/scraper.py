import requests

from datetime import datetime
from discord import Embed
from discord.ext.commands import MessageConverter
from discord.ext.commands.errors import MessageNotFound
from pytz import timezone

from bot import bot, BOT_PREFIX, CS_GUILD_ID, LOGGER
from bot.utils import decrypt, formater, get_collection

login_url="https://myclass.apps.binus.ac.id/Auth/Login"
url = "https://myclass.apps.binus.ac.id/Home/GetViconSchedule"
fail_text = f"**No credentials found**\nCreate it with `{BOT_PREFIX}auth.`"

SAVED_SECRET = get_collection("CREDATA")


@bot.command(aliases=['myclass', 'schedule'])
async def getclass(ctx):
    msg = await ctx.send("Give me a sec...")
    user = ctx.author.id
    text = ""

    secrt = await SAVED_SECRET.find_one({'_id': str(user)})
    if secrt is None:
        if (ctx.guild and str(ctx.guild.id) == CS_GUILD_ID):  #CS LA04
            LOGGER.info("CS Schedule request")
            app = await bot.application_info()
            owner = app.owner.id
            secrt = SAVED_SECRET.find_one({'user_id': str(owner)})
            cht_id = secrt['secret']
            text += "**This is a default Schedule of LA04(my owner)!\nyour Schedule may vary.**"
            text += f"\nYou can `{BOT_PREFIX}auth` yourself to scrape your schedule."
        else:
            await ctx.send(fail_text)
            await msg.delete()
            return
    else:
        cht_id = secrt['secret']
        
    try:
        dec = decrypt(cht_id)
        data = await MessageConverter().convert(ctx, str(dec))
        data = data.content
        secret = data.replace(f"{BOT_PREFIX}auth ", "")
        usr, sec = secret.split("$")

    except MessageNotFound:
        LOGGER.error("Message Not Found")
        delet = SAVED_SECRET.delete_one({'_id': f"{user}"})  # delete user id
        await ctx.send(fail_text)
        await msg.delete()
        return

    session = requests.Session()
    with session.post(login_url, data={
        "Username" : usr,
        "Password" : sec,
    }) as login:
        if login.cookies.get('ASP.NET_SessionId') is None:  # wrong credentials
            await ctx.send(f"**Login Failed\nI think that your credential is wrong.** \
                            \nRecreate by {BOT_PREFIX}auth again")
            await msg.delete()
            return

    with session.post(url) as data:
        schedule = data.json()
        count=0
        dateold = ""

        for sched in schedule:
            if count > 5:  # only scrape 5 days cause discord max msg limitation
                break
            date = sched["DisplayStartDate"]
            if date != dateold:
                count+=1
                text += f"\n# **{date}**\n\n"
                dateold=date

            time = sched["StartTime"][:-3] + "-" + sched["EndTime"][:-3]  # get rid of :seconds
            classcode = sched["ClassCode"]
            classtype = sched["DeliveryMode"]
            course = sched["CourseCode"] + " - " + sched["CourseTitleEn"]
            week = sched["WeekSession"]
            session = sched["CourseSessionNumber"]

            if classtype == "VC":
                meetingurl = sched["MeetingUrl"]  #  get zoom url if it's a VidCon
            else:
                meetingurl = "-"

            text += formater(time, classcode, classtype,
                            course, week, session, meetingurl)

        timenow = datetime.now(timezone("Asia/Jakarta"))
        author = ctx.author.name + "#" + ctx.author.discriminator
        embed = Embed(color=0xff69b4, description=text, timestamp=timenow)
        embed.set_footer(text=f"By {author}")
        await ctx.send(embed=embed)
        await msg.delete()
