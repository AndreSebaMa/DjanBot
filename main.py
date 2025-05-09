import os, time, asyncio
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database

load_dotenv()  # expects a .env with BOT_TOKEN=…

TOKEN = "MTM1Nzc0NjM2MDg3ODYyOTIxOA.G7QJ9O.NidDcXocvtWlOZUioIXxVG6-Eurnydci1ITPJo"
if not TOKEN:
    raise RuntimeError("BOT_TOKEN not set in .env")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# In‐memory tracker of users who have begun but not yet stopped
active_sessions: dict[str, str] = {}

@bot.event
async def on_ready():
    database.init_db()
    print(f"Logged in as {bot.user} (ID {bot.user.id})")
    bot.loop.create_task(auto_stop_loop())
    await tree.sync()
    print("Slash commands synced.")

async def auto_stop_loop():
    await bot.wait_until_ready()
    while True:
        overdue = database.auto_stop_overdue(max_hours=16)
        for user_id, hours, sess_id in overdue:
            user = bot.get_user(int(user_id))
            if user:
                await user.send(
                    f"⏰ Auto-stopped session {sess_id} after 16h (worked {hours:.2f}h)."
                )
        await asyncio.sleep(300)  # every 5 minutes

@tree.command(name="begin", description="Start your workday; optionally add a note.")
@app_commands.describe(note="What you’re working on today")
async def begin(interaction: discord.Interaction, note: str = ""):
    uid = str(interaction.user.id)
    if uid in active_sessions:
        return await interaction.response.send_message(
            "❗️ You already have an active session.", ephemeral=True
        )
    database.start_session(uid, note)
    active_sessions[uid] = note
    await interaction.response.send_message(
        f"🟢 {interaction.user.mention} started your workday.\nNote: “{note}”"
    )

@tree.command(name="end", description="Stop your current workday session.")
@app_commands.describe(finish_note="Optional note on what you finished")
async def stop(interaction: discord.Interaction, finish_note: str = ""):
    uid = str(interaction.user.id)
    if uid not in active_sessions:
        return await interaction.response.send_message(
            "❗️ You don’t have an active session. Use `/begin` first.", ephemeral=True
        )
    try:
        hours = database.stop_session(uid, finish_note)
    except ValueError:
        return await interaction.response.send_message(
            "❗️ No active session found.", ephemeral=True
        )
    active_sessions.pop(uid, None)
    await interaction.response.send_message(
        f"🔴 {interaction.user.mention}, you worked **{hours:.2f}** hours."
    )

@tree.command(name="history", description="Show past work sessions.")
@app_commands.describe(
    member="Whose history to show (default = you)",
    limit="How many sessions to display"
)
async def history(
    interaction: discord.Interaction,
    member: discord.Member | None = None,
    limit: int = 5
):
    target = member or interaction.user
    uid = str(target.id)
    rows = database.get_history(uid, limit)
    if not rows:
        return await interaction.response.send_message(
            f"No past sessions for {target.mention}.", ephemeral=True
        )

    lines = ["ID | Started             | Stopped              | Hrs | Note"]
    for sess_id, start_ts, stop_ts, hours, note in rows:
        started = time.strftime("%Y-%m-%d %H:%M", time.localtime(start_ts))
        stopped = time.strftime("%Y-%m-%d %H:%M", time.localtime(stop_ts))
        lines.append(f"{sess_id} | {started} | {stopped} | {hours:.1f}h | {note}")

    await interaction.response.send_message("```\n" + "\n".join(lines) + "\n```")

@tree.command(name="summary", description="Show total hours over the past N days.")
@app_commands.describe(
    member="Whose summary to show (default = you)",
    days="Number of days back to include"
)
async def summary(
    interaction: discord.Interaction,
    member: discord.Member | None = None,
    days: int = 7
):
    target = member or interaction.user
    uid = str(target.id)
    total = database.get_summary(uid, days)
    await interaction.response.send_message(
        f"📊 {target.mention} worked **{total:.2f} h** in the last **{days}** days."
    )

bot.run(TOKEN)
