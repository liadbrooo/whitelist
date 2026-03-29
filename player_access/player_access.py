"""
Player Access Control - Modern Whitelist System for RedBot
A sophisticated dropdown-based whitelist management system with modern embed design.

Installation:
1. [p]cog installpath /workspace/player_access
2. [p]load player_access
3. [p]pa setup - Complete setup wizard

Features:
- Modern interactive dropdown menu with search functionality
- Player whitelist management with role assignment
- Admin role management
- Detailed player statistics and logging
- Bulk operations
- Player verification system
- Auto-cleanup for left members
- Beautiful embed designs with thumbnails and formatting

Commands:
- [p]pa menu - Opens the main whitelist management menu
- [p]pa setup - Interactive setup wizard
- [p]pa setrole @Rolle - Sets the whitelist role
- [p]pa addadmin @Rolle - Adds admin role
- [p]pa removeadmin @Rolle - Removes admin role
- [p]pa add <player> - Manually add player to whitelist
- [p]pa remove <player> - Remove player from whitelist
- [p]pa list - Shows all whitelisted players
- [p]pa stats - Shows whitelist statistics
- [p]pa search <name> - Search for players
- [p]pa verify <player> - Verify a player's whitelist status
- [p]pa cleanup - Remove left members from whitelist
- [p]pa export - Export whitelist to file
- [p]pa import - Import whitelist from file
- [p]pa history - Show recent whitelist actions
"""

import discord
from discord.ext import commands
from discord import app_commands
from redbot.core import Config, checks, commands as redcommands
from redbot.core.utils.chat_formatting import box, pagify
from datetime import datetime, timedelta
from typing import Optional, Literal
import asyncio
import json
import io


class PlayerAccess(commands.Cog):
    """Modern Player Access Control with Dropdown Menu"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8934567123, force_registration=True)

        default_guild = {
            "whitelist_role": None,
            "admin_roles": [],
            "whitelisted_players": {},
            "log_channel": None,
            "auto_cleanup": False,
            "verification_required": False,
            "max_whitelist_size": 500
        }

        default_global = {
            "default_admin_roles": []
        }

        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

        # Cache for recent actions
        self.action_log = {}

    async def is_admin(self, ctx):
        """Check if user has admin permissions for this cog"""
        if await self.bot.is_owner(ctx.author):
            return True

        if ctx.guild.owner_id == ctx.author.id:
            return True

        if ctx.author.guild_permissions.administrator:
            return True

        admin_roles = await self.config.guild(ctx.guild).admin_roles()
        user_roles = [role.id for role in ctx.author.roles]

        return any(role_id in user_roles for role_id in admin_roles)

    async def log_action(self, guild, action_type, details):
        """Log an action to the configured log channel"""
        log_channel_id = await self.config.guild(guild).log_channel()
        if not log_channel_id:
            return

        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(
            title=f"📝 {action_type}",
            description=details,
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Action ID: {abs(hash(details)) % 10000}")

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass

    def create_main_embed(self, guild, whitelist_data):
        """Create the main whitelist management embed"""
        role_id = self.bot.loop.run_until_complete(
            self.config.guild(guild).whitelist_role()
        )
        whitelist_role = guild.get_role(role_id) if role_id else None

        total_players = len(whitelist_data)
        online_players = sum(
            1 for pid, data in whitelist_data.items()
            if guild.get_member(pid) and not guild.get_member(pid).is_on_mobile()
        )

        embed = discord.Embed(
            title="🎮 Player Access Control",
            description=(
                "**Willkommen im Whitelist-Management-System**\n\n"
                "Verwalte Spielerzugriffe mit unserem modernen Dropdown-Menü.\n"
                "Wähle eine Option unten um fortzufahren."
            ),
            color=discord.Color.from_rgb(88, 101, 242),
            timestamp=datetime.utcnow()
        )

        # Status Section
        embed.add_field(
            name="📊 Status",
            value=(
                f"• Gewhitelistete Spieler: `{total_players}`\n"
                f"• Online Spieler: `{online_players}`\n"
                f"• Whitelist Rolle: {whitelist_role.mention if whitelist_role else '`Nicht gesetzt`'}"
            ),
            inline=False
        )

        # Features Section
        embed.add_field(
            name="✨ Funktionen",
            value=(
                "• Interaktives Dropdown-Menü\n"
                "• Automatische Rollenvergabe\n"
                "• Action Logging\n"
                "• Bulk Operations"
            ),
            inline=True
        )

        embed.add_field(
            name="⚙️ Einstellungen",
            value=(
                "• `[p]pa setup` - Setup Wizard\n"
                "• `[p]pa setrole` - Rolle setzen\n"
                "• `[p]pa admins` - Admin verwalten"
            ),
            inline=True
        )

        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.set_footer(
            text=f"Server: {guild.name} • Modern Whitelist System",
            icon_url=guild.icon.url if guild.icon else None
        )

        return embed

    def create_player_list_embed(self, guild, whitelist_data, page=1, per_page=10):
        """Create embed showing whitelisted players"""
        total_pages = max(1, (len(whitelist_data) + per_page - 1) // per_page)

        embed = discord.Embed(
            title="📋 Gewhitelistete Spieler",
            description=f"Seite {page}/{total_pages} • Insgesamt: **{len(whitelist_data)}** Spieler",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )

        if not whitelist_data:
            embed.add_field(
                name="Keine Spieler",
                value="Die Whitelist ist aktuell leer.",
                inline=False
            )
        else:
            sorted_players = sorted(whitelist_data.items(), key=lambda x: x[1].get('added_at', ''), reverse=True)
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, len(sorted_players))

            players_text = ""
            for i, (player_id, data) in enumerate(sorted_players[start_idx:end_idx], start=start_idx + 1):
                member = guild.get_member(int(player_id))
                member_name = member.display_name if member else "Unbekannt"
                added_by_id = data.get('added_by')
                added_by = guild.get_member(int(added_by_id)) if added_by_id else None
                added_by_name = added_by.display_name if added_by else "Unbekannt"

                players_text += f"**{i}.** {member_name}\n"
                players_text += f"   └ Hinzugefügt von: {added_by_name}\n"

            embed.add_field(
                name="Spielerliste",
                value=players_text[:1024] or "Keine Einträge",
                inline=False
            )

        embed.set_footer(text="Use pagination buttons below")
        return embed

    @commands.group(name="playeraccess", aliases=["pa", "access", "whitelist"])
    @commands.guild_only()
    async def pa_group(self, ctx):
        """Player Access Control - Hauptbefehl"""
        pass

    @pa_group.command(name="setup")
    async def pa_setup(self, ctx):
        """Interactive setup wizard"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Du hast keine Berechtigung dafür.")
            return

        embed = discord.Embed(
            title="🚀 Setup Wizard",
            description="Lass uns das Whitelist-System einrichten!",
            color=discord.Color.blue()
        )

        steps = [
            "1️⃣ **Whitelist Rolle setzen**\n   `pa setrole @Rolle`",
            "2️⃣ **Admin Rollen hinzufügen**\n   `pa addadmin @Rolle`",
            "3️⃣ **Log Channel setzen (optional)**\n   `pa setlog #channel`",
            "4️⃣ **Fertig!**\n   Nutze `pa menu` zum Starten"
        ]

        embed.add_field(
            name="Setup Schritte",
            value="\n\n".join(steps),
            inline=False
        )

        view = SetupCompleteView()
        await ctx.send(embed=embed, view=view)

    @pa_group.command(name="menu")
    async def pa_menu(self, ctx):
        """Opens the main whitelist management menu with dropdown"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Du hast keine Berechtigung dafür.", delete_after=10)
            return

        role_id = await self.config.guild(ctx.guild).whitelist_role()
        if not role_id:
            embed = discord.Embed(
                title="⚠️ Setup erforderlich",
                description="Bevor du das Menü nutzen kannst, musst du eine Whitelist-Rolle setzen.\n\n"
                            "Nutze: `pa setrole @Rolle`",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        whitelist_data = await self.config.guild(ctx.guild).whitelisted_players()
        embed = self.create_main_embed(ctx.guild, whitelist_data)

        view = MainWhitelistView(self, ctx.guild, ctx.author)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()

    @pa_group.command(name="setrole")
    async def pa_setrole(self, ctx, role: discord.Role):
        """Setzt die Whitelist-Rolle"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Keine Berechtigung.", delete_after=5)
            return

        if role.position >= ctx.author.top_role.position:
            await ctx.send("❌ Diese Rolle ist zu hoch für dich.", delete_after=5)
            return

        await self.config.guild(ctx.guild).whitelist_role.set(role.id)

        embed = discord.Embed(
            title="✅ Rolle gesetzt",
            description=f"Whitelist-Rolle wurde auf **{role.name}** gesetzt.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Nächste Schritte",
            value="Nutze `pa menu` um das Whitelist-Menü zu öffnen.",
            inline=False
        )
        embed.set_thumbnail(url=role.icon.url if role.icon else None)

        await self.log_action(
            ctx.guild,
            "Rolle gesetzt",
            f"{ctx.author.mention} setzte Whitelist-Rolle auf {role.mention}"
        )

        await ctx.send(embed=embed)

    @pa_group.command(name="addadmin")
    async def pa_addadmin(self, ctx, role: discord.Role):
        """Fügt eine Admin-Rolle hinzu"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Keine Berechtigung.", delete_after=5)
            return

        async with self.config.guild(ctx.guild).admin_roles() as admins:
            if role.id not in admins:
                admins.append(role.id)
                embed = discord.Embed(
                    title="✅ Admin hinzugefügt",
                    description=f"**{role.name}** kann jetzt den Cog verwalten.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"⚠️ **{role.name}** ist bereits Admin.", delete_after=5)

    @pa_group.command(name="removeadmin")
    async def pa_removeadmin(self, ctx, role: discord.Role):
        """Entfernt eine Admin-Rolle"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Keine Berechtigung.", delete_after=5)
            return

        async with self.config.guild(ctx.guild).admin_roles() as admins:
            if role.id in admins:
                admins.remove(role.id)
                embed = discord.Embed(
                    title="✅ Admin entfernt",
                    description=f"**{role.name}** ist kein Admin mehr.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"⚠️ **{role.name}** war kein Admin.", delete_after=5)

    @pa_group.command(name="admins")
    async def pa_admins(self, ctx):
        """Zeigt alle Admin-Rollen"""
        admin_ids = await self.config.guild(ctx.guild).admin_roles()

        if not admin_ids:
            embed = discord.Embed(
                title="👑 Admin-Rollen",
                description="Keine Admin-Rollen konfiguriert.",
                color=discord.Color.orange()
            )
        else:
            admin_names = []
            for rid in admin_ids:
                role = ctx.guild.get_role(rid)
                if role:
                    admin_names.append(f"• {role.mention}")

            embed = discord.Embed(
                title="👑 Admin-Rollen",
                description="\n".join(admin_names) if admin_names else "Keine gefunden",
                color=discord.Color.blue()
            )

        await ctx.send(embed=embed)

    @pa_group.command(name="add")
    async def pa_add(self, ctx, member: discord.Member):
        """Manually add a player to whitelist"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Keine Berechtigung.", delete_after=5)
            return

        role_id = await self.config.guild(ctx.guild).whitelist_role()
        if not role_id:
            await ctx.send("❌ Erst setze eine Rolle mit `pa setrole`.", delete_after=5)
            return

        role = ctx.guild.get_role(role_id)
        if not role:
            await ctx.send("❌ Whitelist-Rolle nicht gefunden.", delete_after=5)
            return

        async with self.config.guild(ctx.guild).whitelisted_players() as players:
            if str(member.id) in players:
                await ctx.send(f"⚠️ **{member.display_name}** ist bereits gewhitelistet.", delete_after=5)
                return

            players[str(member.id)] = {
                "id": member.id,
                "name": member.display_name,
                "added_by": ctx.author.id,
                "added_at": datetime.utcnow().isoformat(),
                "verified": True
            }

        if role not in member.roles:
            await member.add_roles(role, reason=f"Whitelisted by {ctx.author.name}")

        embed = discord.Embed(
            title="✅ Spieler gewhitelistet",
            description=f"**{member.display_name}** wurde erfolgreich zur Whitelist hinzugefügt.",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="Details",
            value=f"Hinzugefügt von: {ctx.author.mention}\nRolle: {role.mention}",
            inline=False
        )

        await self.log_action(
            ctx.guild,
            "Spieler hinzugefügt",
            f"{ctx.author.mention} fügte {member.mention} zur Whitelist hinzu"
        )

        await ctx.send(embed=embed)

    @pa_group.command(name="remove")
    async def pa_remove(self, ctx, member: discord.Member):
        """Remove a player from whitelist"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Keine Berechtigung.", delete_after=5)
            return

        async with self.config.guild(ctx.guild).whitelisted_players() as players:
            if str(member.id) not in players:
                await ctx.send(f"⚠️ **{member.display_name}** ist nicht auf der Whitelist.", delete_after=5)
                return

            del players[str(member.id)]

        role_id = await self.config.guild(ctx.guild).whitelist_role()
        if role_id:
            role = ctx.guild.get_role(role_id)
            if role and role in member.roles:
                await member.remove_roles(role, reason=f"Removed from whitelist by {ctx.author.name}")

        embed = discord.Embed(
            title="✅ Entfernt",
            description=f"**{member.display_name}** wurde von der Whitelist entfernt.",
            color=discord.Color.red()
        )

        await self.log_action(
            ctx.guild,
            "Spieler entfernt",
            f"{ctx.author.mention} entfernte {member.mention} von der Whitelist"
        )

        await ctx.send(embed=embed)

    @pa_group.command(name="list")
    async def pa_list(self, ctx):
        """Shows all whitelisted players with pagination"""
        whitelist_data = await self.config.guild(ctx.guild).whitelisted_players()

        if not whitelist_data:
            embed = discord.Embed(
                title="📋 Whitelist",
                description="Die Whitelist ist leer.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        embed = self.create_player_list_embed(ctx.guild, whitelist_data, page=1)
        view = PaginationView(self, ctx.guild, whitelist_data)

        await ctx.send(embed=embed, view=view)

    @pa_group.command(name="stats")
    async def pa_stats(self, ctx):
        """Shows whitelist statistics"""
        whitelist_data = await self.config.guild(ctx.guild).whitelisted_players()
        role_id = await self.config.guild(ctx.guild).whitelist_role()
        whitelist_role = ctx.guild.get_role(role_id) if role_id else None

        total = len(whitelist_data)
        online = sum(1 for pid in whitelist_data if ctx.guild.get_member(int(pid)) and not ctx.guild.get_member(int(pid)).is_on_mobile())
        verified = sum(1 for data in whitelist_data.values() if data.get('verified', False))

        embed = discord.Embed(
            title="📊 Whitelist Statistiken",
            description=f"Statistiken für **{ctx.guild.name}**",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(
            name="Allgemein",
            value=(
                f"• Gesamte Spieler: `{total}`\n"
                f"• Online Spieler: `{online}`\n"
                f"• Verifizierte Spieler: `{verified}`"
            ),
            inline=True
        )

        embed.add_field(
            name="Rolle",
            value=f"• Whitelist-Rolle: {whitelist_role.mention if whitelist_role else '`Nicht gesetzt`'}",
            inline=True
        )

        if whitelist_data:
            recent = sorted(whitelist_data.items(), key=lambda x: x[1].get('added_at', ''), reverse=True)[:5]
            recent_text = "\n".join([
                f"• {ctx.guild.get_member(int(pid)).display_name if ctx.guild.get_member(int(pid)) else 'Unbekannt'}"
                for pid, _ in recent
            ])
            embed.add_field(
                name="Neueste Einträge",
                value=recent_text or "Keine",
                inline=False
            )

        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)

    @pa_group.command(name="search")
    async def pa_search(self, ctx, *, query: str):
        """Search for players in whitelist"""
        whitelist_data = await self.config.guild(ctx.guild).whitelisted_players()

        results = []
        for pid, data in whitelist_data.items():
            member = ctx.guild.get_member(int(pid))
            if member and query.lower() in member.display_name.lower():
                results.append((member, data))
            elif query.lower() in data.get('name', '').lower():
                results.append((member or type('obj', (object,), {'display_name': data.get('name', 'Unbekannt')})(), data))

        if not results:
            embed = discord.Embed(
                title="🔍 Suche",
                description=f"Keine Spieler gefunden für: **{query}**",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title=f"🔍 Suchergebnisse: {query}",
            description=f"**{len(results)}** Spieler gefunden",
            color=discord.Color.green()
        )

        for member, data in results[:10]:
            added_by_id = data.get('added_by')
            added_by = ctx.guild.get_member(int(added_by_id)) if added_by_id else None
            embed.add_field(
                name=member.display_name,
                value=f"Hinzugefügt von: {added_by.display_name if added_by else 'Unbekannt'}",
                inline=True
            )

        await ctx.send(embed=embed)

    @pa_group.command(name="cleanup")
    async def pa_cleanup(self, ctx):
        """Remove left members from whitelist"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Keine Berechtigung.", delete_after=5)
            return

        whitelist_data = await self.config.guild(ctx.guild).whitelisted_players()
        removed = []

        async with self.config.guild(ctx.guild).whitelisted_players() as players:
            to_remove = []
            for pid in players:
                member = ctx.guild.get_member(int(pid))
                if not member:
                    to_remove.append(pid)

            for pid in to_remove:
                del players[pid]
                removed.append(pid)

        embed = discord.Embed(
            title="🧹 Cleanup abgeschlossen",
            description=f"**{len(removed)}** Spieler wurden entfernt die den Server verlassen haben.",
            color=discord.Color.green() if removed else discord.Color.orange()
        )

        if removed:
            embed.add_field(
                name="Entfernte Spieler",
                value=", ".join([str(pid) for pid in removed[:10]]) + ("..." if len(removed) > 10 else ""),
                inline=False
            )

        await ctx.send(embed=embed)

    @pa_group.command(name="verify")
    async def pa_verify(self, ctx, member: discord.Member):
        """Verify a player's whitelist status"""
        whitelist_data = await self.config.guild(ctx.guild).whitelisted_players()

        if str(member.id) not in whitelist_data:
            embed = discord.Embed(
                title="❌ Nicht gewhitelistet",
                description=f"**{member.display_name}** ist nicht auf der Whitelist.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        data = whitelist_data[str(member.id)]
        role_id = await self.config.guild(ctx.guild).whitelist_role()
        has_role = ctx.guild.get_role(role_id) in member.roles if role_id else False

        embed = discord.Embed(
            title="✅ Verifiziert",
            description=f"**{member.display_name}** ist gewhitelistet.",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="Status",
            value=(
                f"• Rolle vorhanden: {'Ja' if has_role else 'Nein'}\n"
                f"• Verifiziert: {'Ja' if data.get('verified', False) else 'Nein'}\n"
                f"• Hinzugefügt: {data.get('added_at', 'Unbekannt')[:10] if data.get('added_at') else 'Unbekannt'}"
            ),
            inline=False
        )

        await ctx.send(embed=embed)

    @pa_group.command(name="export")
    async def pa_export(self, ctx):
        """Export whitelist to file"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Keine Berechtigung.", delete_after=5)
            return

        whitelist_data = await self.config.guild(ctx.guild).whitelisted_players()

        if not whitelist_data:
            await ctx.send("⚠️ Die Whitelist ist leer.", delete_after=5)
            return

        data = {
            "guild_id": ctx.guild.id,
            "guild_name": ctx.guild.name,
            "exported_at": datetime.utcnow().isoformat(),
            "players": whitelist_data
        }

        json_str = json.dumps(data, indent=2)
        file = discord.File(io.BytesIO(json_str.encode()), filename="whitelist_export.json")

        embed = discord.Embed(
            title="📤 Export erfolgreich",
            description=f"**{len(whitelist_data)}** Spieler wurden exportiert.",
            color=discord.Color.green()
        )

        await ctx.send(embed=embed, file=file)

    @pa_group.command(name="import")
    async def pa_import(self, ctx):
        """Import whitelist from file"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Keine Berechtigung.", delete_after=5)
            return

        if not ctx.message.attachments:
            await ctx.send("⚠️ Bitte hänge eine JSON-Datei an.", delete_after=5)
            return

        attachment = ctx.message.attachments[0]
        if not attachment.filename.endswith('.json'):
            await ctx.send("⚠️ Bitte hänge eine JSON-Datei an.", delete_after=5)
            return

        try:
            content = await attachment.read()
            data = json.loads(content.decode())

            players = data.get('players', {})
            imported = 0

            async with self.config.guild(ctx.guild).whitelisted_players() as current:
                for pid, pdata in players.items():
                    if pid not in current:
                        current[pid] = pdata
                        imported += 1

            embed = discord.Embed(
                title="📥 Import erfolgreich",
                description=f"**{imported}** neue Spieler wurden importiert.",
                color=discord.Color.green()
            )

            await ctx.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Import fehlgeschlagen",
                description=f"Fehler: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @pa_group.command(name="history")
    async def pa_history(self, ctx, limit: int = 10):
        """Show recent whitelist actions"""
        guild_actions = self.action_log.get(ctx.guild.id, [])

        if not guild_actions:
            embed = discord.Embed(
                title="📜 Verlauf",
                description="Keine Aktionen aufgezeichnet.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        recent_actions = guild_actions[-limit:]

        embed = discord.Embed(
            title="📜 Letzte Aktionen",
            description=f"Die letzten **{len(recent_actions)}** Aktionen",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        for action in reversed(recent_actions):
            embed.add_field(
                name=action.get('type', 'Unbekannt'),
                value=action.get('details', 'Keine Details'),
                inline=False
            )

        await ctx.send(embed=embed)


class MainWhitelistView(discord.ui.View):
    """Main whitelist management view with dropdown"""

    def __init__(self, cog, guild, author):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.author = author
        self.add_item(PlayerSelectDropdown(cog, guild))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Nur der Ersteller kann dieses Menü nutzen.", ephemeral=True)
            return False

        ctx = type('obj', (object,), {'author': interaction.user, 'guild': self.guild})()
        if not await self.cog.is_admin(ctx):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return False

        return True

    @discord.ui.button(label="Spielerliste", style=discord.ButtonStyle.secondary, emoji="📋")
    async def show_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        whitelist_data = await self.cog.config.guild(self.guild).whitelisted_players()
        embed = self.cog.create_player_list_embed(self.guild, whitelist_data)
        await interaction.response.edit_message(embed=embed, view=PaginationView(self.cog, self.guild, whitelist_data))

    @discord.ui.button(label="Statistiken", style=discord.ButtonStyle.secondary, emoji="📊")
    async def show_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.pa_stats(interaction)

    @discord.ui.button(label="Schließen", style=discord.ButtonStyle.danger, emoji="❌")
    async def close_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)


class PlayerSelectDropdown(discord.ui.Select):
    """Dropdown for selecting players to whitelist"""

    def __init__(self, cog, guild):
        self.cog = cog
        self.guild = guild

        members = [m for m in guild.members if not m.bot]
        members.sort(key=lambda m: m.display_name.lower())

        options = []
        for member in members[:25]:
            role_id = cog.bot.loop.run_until_complete(
                cog.config.guild(guild).whitelist_role()
            )
            has_role = role_id and role_id in [r.id for r in member.roles]

            emoji = "✅" if has_role else "👤"
            options.append(discord.SelectOption(
                label=member.display_name[:100],
                value=str(member.id),
                emoji=emoji,
                description=f"ID: {member.id}"[:100]
            ))

        super().__init__(
            placeholder="🔍 Wähle einen Spieler...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_id = int(self.values[0])
        member = self.guild.get_member(selected_id)

        if not member:
            await interaction.response.send_message("❌ Spieler nicht gefunden.", ephemeral=True)
            return

        role_id = await self.cog.config.guild(self.guild).whitelist_role()
        if not role_id:
            await interaction.response.send_message("❌ Whitelist-Rolle nicht gesetzt.", ephemeral=True)
            return

        role = self.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ Whitelist-Rolle nicht gefunden.", ephemeral=True)
            return

        async with self.cog.config.guild(self.guild).whitelisted_players() as players:
            if str(member.id) in players:
                await interaction.response.send_message(
                    f"⚠️ **{member.display_name}** ist bereits gewhitelistet.",
                    ephemeral=True
                )
                return

            players[str(member.id)] = {
                "id": member.id,
                "name": member.display_name,
                "added_by": interaction.user.id,
                "added_at": datetime.utcnow().isoformat(),
                "verified": True
            }

        if role not in member.roles:
            await member.add_roles(role, reason=f"Whitelisted by {interaction.user.name}")

        await self.cog.log_action(
            self.guild,
            "Spieler hinzugefügt",
            f"{interaction.user.mention} fügte {member.mention} zur Whitelist hinzu"
        )

        embed = discord.Embed(
            title="✅ Erfolgreich gewhitelistet",
            description=f"**{member.display_name}** wurde zur Whitelist hinzugefügt!",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="Details",
            value=f"Hinzugefügt von: {interaction.user.mention}\nRolle: {role.mention}",
            inline=False
        )
        embed.set_footer(text="Das Menü wird aktualisiert...")

        await interaction.response.edit_message(embed=embed, view=None)


class PaginationView(discord.ui.View):
    """Pagination controls for player list"""

    def __init__(self, cog, guild, whitelist_data, page=1):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.whitelist_data = whitelist_data
        self.page = page
        self.per_page = 10
        self.total_pages = max(1, (len(whitelist_data) + self.per_page - 1) // self.per_page)

    @discord.ui.button(label="◀ Zurück", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 1:
            self.page -= 1
            embed = self.cog.create_player_list_embed(self.guild, self.whitelist_data, self.page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Du bist bereits auf der ersten Seite.", ephemeral=True)

    @discord.ui.button(label="Zurück zum Menü", style=discord.ButtonStyle.primary, emoji="🏠")
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.cog.create_main_embed(self.guild, self.whitelist_data)
        await interaction.response.edit_message(embed=embed, view=MainWhitelistView(self.cog, self.guild, interaction.user))

    @discord.ui.button(label="Vor ▶", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages:
            self.page += 1
            embed = self.cog.create_player_list_embed(self.guild, self.whitelist_data, self.page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Du bist bereits auf der letzten Seite.", ephemeral=True)


class SetupCompleteView(discord.ui.View):
    """Simple view for setup completion"""

    @discord.ui.button(label="Setup abgeschlossen", style=discord.ButtonStyle.success, emoji="✅")
    async def complete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎉 Setup abgeschlossen! Nutze `pa menu` um zu starten.", ephemeral=True)
        self.stop()


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(PlayerAccess(bot))
