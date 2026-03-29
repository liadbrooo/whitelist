"""
Whitelist Management Cog for RedBot
Modern dropdown menu system for player whitelisting with role assignment
"""

import discord
from discord import app_commands
from redbot.core import commands, checks, Config
from redbot.core.utils.views import SimpleMenu
from redbot.core.utils.mod import get_audit_reason
from typing import Optional, List
import asyncio


class WhitelistView(discord.ui.View):
    """Interactive view for whitelist management"""
    
    def __init__(self, cog, players: List[dict], timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.players = players
        self.current_page = 0
        self.items_per_page = 10
        
        # Update select options
        self.update_select_options()
    
    def update_select_options(self):
        """Update the dropdown options based on current players"""
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.players))
        
        self.player_select.options = []
        for i in range(start_idx, end_idx):
            player = self.players[i]
            status = "✅" if player.get("whitelisted", False) else "❌"
            role_info = f" - {player.get('role', 'Keine')}" if player.get("role") else ""
            
            option = discord.SelectOption(
                label=f"{player['name']} {status}",
                value=str(player["id"]),
                description=f"ID: {player['id']}{role_info}",
                emoji="🎮"
            )
            self.player_select.options.append(option)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only authorized users can interact"""
        return await self.cog.check_permissions(interaction)
    
    @discord.ui.select(
        placeholder="Spieler zum Whitelisten auswählen...",
        min_values=1,
        max_values=1,
        row=0
    )
    async def player_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle player selection from dropdown"""
        player_id = int(select.values[0])
        player = next((p for p in self.players if p["id"] == player_id), None)
        
        if not player:
            await interaction.response.send_message(
                "❌ Spieler nicht gefunden!",
                ephemeral=True
            )
            return
        
        # Create modal for confirmation
        modal = WhitelistModal(self.cog, player, self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary, row=1)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_select_options()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message(
                "Du bist bereits auf der ersten Seite!",
                ephemeral=True
            )
    
    @discord.ui.button(label="➡️ Weiter", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to next page"""
        total_pages = (len(self.players) - 1) // self.items_per_page
        if self.current_page < total_pages:
            self.current_page += 1
            self.update_select_options()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message(
                "Du bist bereits auf der letzten Seite!",
                ephemeral=True
            )
    
    @discord.ui.button(label="🔄 Aktualisieren", style=discord.ButtonStyle.primary, row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the player list"""
        await self.cog.refresh_player_list(interaction, self)
    
    @discord.ui.button(label="❌ Schließen", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the view"""
        await interaction.response.edit_message(view=None)


class WhitelistModal(discord.ui.Modal):
    """Modal for confirming whitelist action"""
    
    def __init__(self, cog, player: dict, view: WhitelistView):
        super().__init__(title="Spieler Whitelisten", timeout=180.0)
        self.cog = cog
        self.player = player
        self.view = view
        
        self.reason = discord.ui.TextInput(
            label="Grund für die Whitelist",
            style=discord.TextStyle.short,
            placeholder="Warum soll dieser Spieler gewhitelisted werden?",
            required=False,
            default="Manuelle Whitelist durch Admin"
        )
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        success, message = await self.cog.whitelist_player(
            interaction, 
            self.player, 
            self.reason.value
        )
        
        if success:
            # Refresh the view to show updated status
            self.view.update_select_options()
            await interaction.followup.send(
                f"✅ {message}",
                ephemeral=True
            )
            # Update the original message to reflect changes
            await interaction.edit_original_response(view=self.view)
        else:
            await interaction.followup.send(
                f"❌ {message}",
                ephemeral=True
            )


class WhitelistManager(commands.Cog):
    """
    Modern Whitelist Management System
    
    Ein fortschrittliches System zur Verwaltung von Spieler-Whitelists
    mit interaktiven Dropdown-Menüs, Rollenzuweisung und umfassenden Funktionen.
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=584736291847362, force_registration=True)
        
        default_guild = {
            "whitelist_role": None,
            "whitelisted_players": {},
            "admin_roles": [],
            "log_channel": None,
            "auto_approve": False,
            "max_whitelist_slots": 100
        }
        self.config.register_guild(**default_guild)
    
    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to use whitelist commands"""
        ctx = await self.bot.get_context(interaction.message) if hasattr(interaction, 'message') else None
        
        # Check for admin roles
        admin_roles = await self.config.guild(interaction.guild).admin_roles()
        if admin_roles:
            user_roles = [role.id for role in interaction.user.roles]
            if any(role_id in user_roles for role_id in admin_roles):
                return True
        
        # Fallback to traditional admin check
        return await self.bot.is_admin(interaction.user)
    
    async def log_action(self, guild: discord.Guild, action: str, user: discord.Member, details: str):
        """Log whitelist actions to configured channel"""
        log_channel_id = await self.config.guild(guild).log_channel()
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="📋 Whitelist Log",
                    description=f"**Aktion:** {action}\n**Durchgeführt von:** {user.mention}\n**Details:** {details}",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_footer(text=f"User ID: {user.id}")
                try:
                    await log_channel.send(embed=embed)
                except discord.Forbidden:
                    pass
    
    async def refresh_player_list(self, interaction: discord.Interaction, view: WhitelistView):
        """Refresh the player list in the view"""
        # In a real implementation, this would fetch from your game server API
        # For now, we'll simulate with existing data
        whitelisted_data = await self.config.guild(interaction.guild).whitelisted_players()
        
        # Recreate players list
        players = []
        for player_id, player_data in whitelisted_data.items():
            players.append({
                "id": int(player_id),
                "name": player_data.get("name", "Unbekannt"),
                "whitelisted": True,
                "role": player_data.get("role_name", "Keine"),
                "added_by": player_data.get("added_by", "Unbekannt"),
                "reason": player_data.get("reason", "Kein Grund angegeben"),
                "timestamp": player_data.get("timestamp", 0)
            })
        
        # Add some example players if list is empty
        if not players:
            players = [
                {"id": 1, "name": "BeispielSpieler1", "whitelisted": False},
                {"id": 2, "name": "TestUser2", "whitelisted": False},
                {"id": 3, "name": "GamerPro3", "whitelisted": False},
            ]
        
        view.players = players
        view.current_page = 0
        view.update_select_options()
    
    async def whitelist_player(self, interaction: discord.Interaction, player: dict, reason: str) -> tuple[bool, str]:
        """Add a player to the whitelist and assign role"""
        guild = interaction.guild
        member = interaction.user
        
        # Get configured role
        role_id = await self.config.guild(guild).whitelist_role()
        role = guild.get_role(role_id) if role_id else None
        
        # Find or create user representation
        # In real implementation, this would be your game server user
        try:
            # Try to find Discord member by name (simplified for demo)
            target_member = discord.utils.get(guild.members, name=player["name"])
            
            if target_member and role:
                await target_member.add_roles(role, reason=reason)
                
                # Save to config
                async with self.config.guild(guild).whitelisted_players() as players:
                    players[str(player["id"])] = {
                        "name": player["name"],
                        "discord_id": target_member.id,
                        "role_name": role.name,
                        "added_by": member.id,
                        "reason": reason,
                        "timestamp": int(discord.utils.utcnow().timestamp())
                    }
                
                # Log action
                await self.log_action(
                    guild, 
                    "Spieler gewhitelisted", 
                    member, 
                    f"Spieler: {player['name']} ({target_member.mention}), Grund: {reason}"
                )
                
                return True, f"Spieler **{player['name']}** wurde erfolgreich gewhitelisted und hat die Rolle **{role.name}** erhalten!"
            else:
                # Save without role assignment
                async with self.config.guild(guild).whitelisted_players() as players:
                    players[str(player["id"])] = {
                        "name": player["name"],
                        "discord_id": None,
                        "role_name": role.name if role else "Keine Rolle konfiguriert",
                        "added_by": member.id,
                        "reason": reason,
                        "timestamp": int(discord.utils.utcnow().timestamp())
                    }
                
                await self.log_action(
                    guild,
                    "Spieler zur Whitelist hinzugefügt",
                    member,
                    f"Spieler: {player['name']}, Grund: {reason} (Keine Rollenzuweisung möglich)"
                )
                
                return True, f"Spieler **{player['name']}** wurde zur Whitelist hinzugefügt! (Rolle konnte nicht zugewiesen werden)"
                
        except Exception as e:
            return False, f"Fehler beim Whitelisten: {str(e)}"
    
    @commands.group(name="whitelist", aliases=["wl"], invoke_without_command=True)
    @commands.guild_only()
    async def whitelist_group(self, ctx: commands.Context):
        """
        🎮 Whitelist Management System
        
        Verwalte Spieler-Whitelists mit modernen Interaktionsmöglichkeiten.
        """
        embed = discord.Embed(
            title="🎮 Whitelist Management",
            description="Willkommen im Whitelist Management System!\n\nWähle eine Option aus dem Menü oder verwende einen der folgenden Befehle:",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Befehle",
            value="""
            `/whitelist menu` - Öffne das interaktive Menü
            `/whitelist add <spieler>` - Spieler manuell hinzufügen
            `/whitelist remove <spieler>` - Spieler entfernen
            `/whitelist list` - Alle gewhitelisted Spieler anzeigen
            `/whitelist settings` - Konfiguration anpassen
            """,
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Aktuelle Einstellungen",
            value=f"**Whitelist Rolle:** {'Konfiguriert' if await self.config.guild(ctx.guild).whitelist_role() else 'Nicht konfiguriert'}\n**Admin Rollen:** {len(await self.config.guild(ctx.guild).admin_roles())} konfiguriert",
            inline=False
        )
        
        embed.set_footer(text=f"Angefragt von {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        view = discord.ui.View()
        
        menu_button = discord.ui.Button(
            label="🎮 Menü öffnen",
            style=discord.ButtonStyle.primary,
            custom_id="whitelist_menu"
        )
        
        async def menu_callback(interaction: discord.Interaction):
            if not await self.check_permissions(interaction):
                await interaction.response.send_message(
                    "❌ Du hast keine Berechtigung, dieses Menü zu verwenden!",
                    ephemeral=True
                )
                return
            
            # Simulate player list (in production, fetch from your game server)
            whitelisted_data = await self.config.guild(interaction.guild).whitelisted_players()
            players = []
            
            for player_id, player_data in whitelisted_data.items():
                players.append({
                    "id": int(player_id),
                    "name": player_data.get("name", "Unbekannt"),
                    "whitelisted": True,
                    "role": player_data.get("role_name", "Keine"),
                    "added_by": player_data.get("added_by", "Unbekannt"),
                    "reason": player_data.get("reason", "Kein Grund"),
                    "timestamp": player_data.get("timestamp", 0)
                })
            
            # Add example players if none exist
            if not players:
                players = [
                    {"id": i, "name": f"Spieler{i}", "whitelisted": False}
                    for i in range(1, 16)
                ]
            
            embed = discord.Embed(
                title="🎮 Spieler Whitelist",
                description="Wähle einen Spieler aus dem Dropdown-Menü, um ihn zu whitelisten.\n\nVerwende die Pfeiltasten zum Navigieren zwischen den Seiten.",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="📊 Statistik",
                value=f"**Gesamte Spieler:** {len(players)}\n**Gewhitelisted:** {sum(1 for p in players if p.get('whitelisted'))}\n**Verfügbar:** {sum(1 for p in players if not p.get('whitelisted'))}",
                inline=False
            )
            
            view = WhitelistView(self, players)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        menu_button.callback = menu_callback
        view.add_item(menu_button)
        
        await ctx.send(embed=embed, view=view)
    
    @whitelist_group.command(name="menu")
    @commands.guild_only()
    async def whitelist_menu(self, ctx: commands.Context):
        """Öffne das interaktive Whitelist-Menü"""
        if not await self.check_permissions(type('obj', (object,), {'guild': ctx.guild, 'user': ctx.author, 'response': type('obj', (object,), {'send_message': lambda **kwargs: None})})()):
            await ctx.send("❌ Du hast keine Berechtigung, dieses Menü zu verwenden!")
            return
        
        # Trigger the group command functionality
        await self.whitelist_group(ctx)
    
    @app_commands.command(name="whitelist", description="Öffne das Whitelist Management Menü")
    @app_commands.guild_only()
    async def whitelist_slash(self, interaction: discord.Interaction):
        """Slash command version of whitelist menu"""
        if not await self.check_permissions(interaction):
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung, dieses Menü zu verwenden!",
                ephemeral=True
            )
            return
        
        # Same functionality as context menu
        embed = discord.Embed(
            title="🎮 Whitelist Management",
            description="Willkommen im Whitelist Management System!",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        view = discord.ui.View()
        menu_button = discord.ui.Button(
            label="🎮 Menü öffnen",
            style=discord.ButtonStyle.primary
        )
        
        async def menu_callback(interaction: discord.Interaction):
            # Create sample player list
            players = [
                {"id": i, "name": f"Spieler{i}", "whitelisted": i % 3 == 0}
                for i in range(1, 21)
            ]
            
            embed = discord.Embed(
                title="🎮 Spieler Whitelist",
                description="Wähle einen Spieler aus dem Dropdown-Menü, um ihn zu whitelisten.",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            view = WhitelistView(self, players)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        menu_button.callback = menu_callback
        view.add_item(menu_button)
        await interaction.response.send_message(embed=embed, view=view)
    
    @commands.command(name="setwhitelistrole")
    @commands.admin_or_permissions(administrator=True)
    async def set_whitelist_role(self, ctx: commands.Context, role: discord.Role):
        """Setze die Rolle, die gewhitelisted Spielern zugewiesen wird"""
        await self.config.guild(ctx.guild).whitelist_role.set(role.id)
        
        embed = discord.Embed(
            title="✅ Rolle konfiguriert",
            description=f"Die Whitelist-Rolle wurde auf **{role.name}** gesetzt.\n\nSpielern, die jetzt gewhitelisted werden, erhalten automatisch diese Rolle.",
            color=discord.Color.green()
        )
        
        await self.log_action(ctx.guild, "Rolle konfiguriert", ctx.author, f"Whitelist-Rolle: {role.name} ({role.id})")
        await ctx.send(embed=embed)
    
    @commands.command(name="addadminrole")
    @commands.admin_or_permissions(administrator=True)
    async def add_admin_role(self, ctx: commands.Context, role: discord.Role):
        """Füge eine Admin-Rolle hinzu, die Whitelist-Befehle verwenden kann"""
        async with self.config.guild(ctx.guild).admin_roles() as roles:
            if role.id not in roles:
                roles.append(role.id)
        
        embed = discord.Embed(
            title="✅ Admin-Rolle hinzugefügt",
            description=f"**{role.name}** kann jetzt Whitelist-Befehle verwenden.",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="removewhitelist")
    @commands.admin_or_permissions(administrator=True)
    async def remove_whitelist(self, ctx: commands.Context, player_name: str):
        """Entferne einen Spieler von der Whitelist"""
        member = ctx.author
        
        async with self.config.guild(ctx.guild).whitelisted_players() as players:
            # Find player by name
            player_to_remove = None
            for player_id, player_data in players.items():
                if player_data.get("name", "").lower() == player_name.lower():
                    player_to_remove = player_id
                    break
            
            if player_to_remove:
                removed_player = players.pop(player_to_remove)
                
                # Try to remove role
                role_id = await self.config.guild(ctx.guild).whitelist_role()
                if role_id:
                    role = ctx.guild.get_role(role_id)
                    if role:
                        # Try to find and update member
                        target_member = discord.utils.get(ctx.guild.members, name=removed_player.get("name"))
                        if target_member and role in target_member.roles:
                            await target_member.remove_roles(role, reason=f"Von Whitelist entfernt durch {member.display_name}")
                
                await self.log_action(
                    ctx.guild,
                    "Spieler von Whitelist entfernt",
                    member,
                    f"Spieler: {removed_player.get('name')}"
                )
                
                embed = discord.Embed(
                    title="✅ Spieler entfernt",
                    description=f"**{removed_player.get('name')}** wurde von der Whitelist entfernt.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ Spieler **{player_name}** wurde nicht in der Whitelist gefunden.")
    
    @commands.command(name="whitelistlist")
    @commands.guild_only()
    async def whitelist_list(self, ctx: commands.Context):
        """Zeige alle gewhitelisted Spieler an"""
        whitelisted_data = await self.config.guild(ctx.guild).whitelisted_players()
        
        if not whitelisted_data:
            await ctx.send("📭 Derzeit sind keine Spieler in der Whitelist.")
            return
        
        embed = discord.Embed(
            title="📋 Gewhitelisted Spieler",
            description=f"Insgesamt **{len(whitelisted_data)}** Spieler gewhitelisted",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Group players into chunks for display
        players_list = []
        for player_id, player_data in whitelisted_data.items():
            name = player_data.get("name", "Unbekannt")
            role = player_data.get("role_name", "Keine Rolle")
            added_by = player_data.get("added_by", "Unbekannt")
            timestamp = player_data.get("timestamp", 0)
            
            if timestamp:
                date_str = f"<t:{timestamp}:R>"
            else:
                date_str = "Unbekannt"
            
            players_list.append(f"🎮 **{name}**\n└ Rolle: {role} | Hinzugefügt: <@{added_by}> | {date_str}")
        
        # Split into multiple embeds if too long
        chunk_size = 10
        for i in range(0, len(players_list), chunk_size):
            chunk = players_list[i:i+chunk_size]
            embed_chunk = discord.Embed(
                title=f"📋 Gewhitelisted Spieler ({i+1}-{min(i+chunk_size, len(players_list))} von {len(players_list)})",
                description="\n".join(chunk),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            await ctx.send(embed=embed_chunk)
    
    @commands.command(name="whitelistsettings")
    @commands.admin_or_permissions(administrator=True)
    async def whitelist_settings(self, ctx: commands.Context):
        """Zeige aktuelle Whitelist-Einstellungen an"""
        guild_data = await self.config.guild(ctx.guild).all()
        
        embed = discord.Embed(
            title="⚙️ Whitelist Einstellungen",
            color=discord.Color.purple(),
            timestamp=discord.utils.utcnow()
        )
        
        # Role information
        role_id = guild_data.get("whitelist_role")
        role = ctx.guild.get_role(role_id) if role_id else None
        embed.add_field(
            name="🎭 Whitelist-Rolle",
            value=role.mention if role else "Nicht konfiguriert",
            inline=False
        )
        
        # Admin roles
        admin_role_ids = guild_data.get("admin_roles", [])
        admin_roles = [ctx.guild.get_role(rid).mention for rid in admin_role_ids if ctx.guild.get_role(rid)]
        embed.add_field(
            name="👮 Admin-Rollen",
            value="\n".join(admin_roles) if admin_roles else "Standard Admin-Berechtigungen",
            inline=False
        )
        
        # Statistics
        whitelisted_count = len(guild_data.get("whitelisted_players", {}))
        embed.add_field(
            name="📊 Statistik",
            value=f"**Gewhitelisted:** {whitelisted_count}\n**Max Slots:** {guild_data.get('max_whitelist_slots', 100)}",
            inline=False
        )
        
        embed.set_footer(text=f"Guild ID: {ctx.guild.id}")
        await ctx.send(embed=embed)


async def setup(bot):
    """Load the WhitelistManager cog"""
    await bot.add_cog(WhitelistManager(bot))
