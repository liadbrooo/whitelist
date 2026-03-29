"""
Advanced Player Access Control Cog for RedBot
Modern dropdown menu system for player management with role assignment
No slash commands - uses prefix commands only
Command: playeraccess (aliases: pa, access)
"""

import discord
from redbot.core import commands, Config, checks
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate
from typing import Optional, List, Dict
import asyncio
from datetime import datetime, timedelta
import re


class PlayerAccessView(discord.ui.View):
    """Interactive view for player access management"""
    
    def __init__(self, cog, players: List[dict], timeout: float = 300.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.players = players
        self.current_page = 0
        self.items_per_page = 8
        self.search_query = ""
        self.filter_type = "all"  # all, whitelisted, pending
        self.update_select_options()
    
    def get_filtered_players(self) -> List[dict]:
        """Get filtered and searched players"""
        filtered = self.players
        
        # Apply search filter
        if self.search_query:
            filtered = [p for p in filtered if self.search_query.lower() in p["name"].lower()]
        
        # Apply type filter
        if self.filter_type == "whitelisted":
            filtered = [p for p in filtered if p.get("whitelisted", False)]
        elif self.filter_type == "pending":
            filtered = [p for p in filtered if not p.get("whitelisted", False)]
        
        return filtered
    
    def update_select_options(self):
        """Update the dropdown options based on current players"""
        filtered_players = self.get_filtered_players()
        total_pages = max(1, (len(filtered_players) - 1) // self.items_per_page + 1)
        
        # Ensure current page is valid
        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)
        
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(filtered_players))
        
        self.player_select.options = []
        for i in range(start_idx, end_idx):
            player = filtered_players[i]
            status_emoji = "✅" if player.get("whitelisted", False) else "⏳"
            priority = player.get("priority", 0)
            priority_badge = f" | ⭐{priority}" if priority > 0 else ""
            
            # Truncate long names
            display_name = player["name"][:40] + "..." if len(player["name"]) > 40 else player["name"]
            
            option = discord.SelectOption(
                label=f"{display_name} {status_emoji}",
                value=str(player["id"]),
                description=f"{'Gewhitelisted' if player.get('whitelisted') else 'Ausstehend'}{priority_badge}",
                emoji="🎮"
            )
            self.player_select.options.append(option)
        
        # Update page info in embed if possible
        self.page_info = f"Seite {self.current_page + 1}/{total_pages}"
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only authorized users can interact"""
        return await self.cog.check_permissions(interaction)
    
    @discord.ui.select(
        placeholder="🔍 Spieler auswählen oder suchen...",
        min_values=1,
        max_values=1,
        row=0
    )
    async def player_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle player selection from dropdown"""
        player_id = int(select.values[0])
        player = next((p for p in self.get_filtered_players() if p["id"] == player_id), None)
        
        if not player:
            await interaction.response.send_message(
                "❌ Spieler nicht gefunden!",
                ephemeral=True
            )
            return
        
        # Create action view
        action_view = PlayerActionView(self.cog, player, self)
        embed = self.create_player_embed(player)
        
        await interaction.response.send_message(
            embed=embed,
            view=action_view,
            ephemeral=True
        )
    
    def create_player_embed(self, player: dict) -> discord.Embed:
        """Create a detailed embed for a player"""
        status_color = discord.Color.green() if player.get("whitelisted") else discord.Color.orange()
        status_text = "Gewhitelisted" if player.get("whitelisted") else "Ausstehend"
        
        embed = discord.Embed(
            title=f"🎮 Spieler: {player['name']}",
            color=status_color,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="📋 Status",
            value=f"**Zugang:** {status_text}\n**Priorität:** {'⭐' * player.get('priority', 0)} ({player.get('priority', 0)})\n**Spieler-ID:** `{player['id']}`",
            inline=False
        )
        
        if player.get("whitelisted"):
            embed.add_field(
                name="ℹ️ Whitelist Infos",
                value=f"**Hinzugefügt von:** <@{player.get('added_by', 'Unbekannt')}>\n**Grund:** {player.get('reason', 'Kein Grund angegeben')}\n**Datum:** <t:{player.get('timestamp', 0)}:R>",
                inline=False
            )
        
        if player.get("notes"):
            embed.add_field(
                name="📝 Notizen",
                value=player["notes"][:500],  # Limit length
                inline=False
            )
        
        embed.set_footer(text=f"Manager: {self.cog.bot.user.name}")
        return embed
    
    @discord.ui.button(label="🔍 Suche", style=discord.ButtonStyle.secondary, row=1, custom_id="search_btn")
    async def search_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open search modal"""
        modal = SearchModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📊 Alle", style=discord.ButtonStyle.primary, row=1, custom_id="filter_all")
    async def filter_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show all players"""
        self.filter_type = "all"
        self.current_page = 0
        self.update_select_options()
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(label="✅ Whitelisted", style=discord.ButtonStyle.success, row=1, custom_id="filter_wl")
    async def filter_wl_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show only whitelisted players"""
        self.filter_type = "whitelisted"
        self.current_page = 0
        self.update_select_options()
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(label="⏳ Ausstehend", style=discord.ButtonStyle.secondary, row=1, custom_id="filter_pending")
    async def filter_pending_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show only pending players"""
        self.filter_type = "pending"
        self.current_page = 0
        self.update_select_options()
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary, row=2, custom_id="prev_page")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to previous page"""
        filtered_players = self.get_filtered_players()
        total_pages = max(1, (len(filtered_players) - 1) // self.items_per_page + 1)
        
        if self.current_page > 0:
            self.current_page -= 1
            self.update_select_options()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message(
                "⚠️ Du bist bereits auf der ersten Seite!",
                ephemeral=True
            )
    
    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary, row=2, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to next page"""
        filtered_players = self.get_filtered_players()
        total_pages = max(1, (len(filtered_players) - 1) // self.items_per_page + 1)
        
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.update_select_options()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message(
                "⚠️ Du bist bereits auf der letzten Seite!",
                ephemeral=True
            )
    
    @discord.ui.button(label="🔄 Aktualisieren", style=discord.ButtonStyle.primary, row=2, custom_id="refresh")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the player list"""
        await self.cog.refresh_player_list(interaction, self)
    
    @discord.ui.button(label="📈 Statistiken", style=discord.ButtonStyle.success, row=2, custom_id="stats")
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show statistics"""
        await self.cog.show_statistics(interaction, self.players)
    
    @discord.ui.button(label="❌ Schließen", style=discord.ButtonStyle.danger, row=2, custom_id="close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the view"""
        await interaction.response.edit_message(view=None)


class SearchModal(discord.ui.Modal):
    """Modal for searching players"""
    
    def __init__(self, view: PlayerAccessView):
        super().__init__(title="🔍 Spieler suchen", timeout=180.0)
        self.view = view
        
        self.search_input = discord.ui.TextInput(
            label="Suchbegriff",
            style=discord.TextStyle.short,
            placeholder="Name oder ID des Spielers...",
            required=True,
            max_length=50
        )
        self.add_item(self.search_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        query = self.search_input.value.strip()
        self.view.search_query = query
        self.view.current_page = 0
        self.view.update_select_options()
        
        await interaction.response.edit_message(view=self.view)


class PlayerActionView(discord.ui.View):
    """Action view for individual player management"""
    
    def __init__(self, cog, player: dict, parent_view: PlayerAccessView):
        super().__init__(timeout=300.0)
        self.cog = cog
        self.player = player
        self.parent_view = parent_view
        
        # Update button states based on player status
        self.whitelist_button.disabled = player.get("whitelisted", False)
        self.remove_button.disabled = not player.get("whitelisted", False)
    
    @discord.ui.button(label="✅ Whitelisten", style=discord.ButtonStyle.success, row=0, custom_id="wl_action")
    async def whitelist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Whitelist the selected player"""
        modal = WhitelistModal(self.cog, self.player, self.parent_view)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="❌ Entfernen", style=discord.ButtonStyle.danger, row=0, custom_id="remove_action")
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove player from whitelist"""
        confirm_view = ConfirmRemovalView(self.cog, self.player, self.parent_view)
        embed = discord.Embed(
            title="⚠️ Bestätigung erforderlich",
            description=f"Möchtest du **{self.player['name']}** wirklich von der Whitelist entfernen?\n\nDiese Aktion kann nicht rückgängig gemacht werden!",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(
            embed=embed,
            view=confirm_view
        )
    
    @discord.ui.button(label="📝 Notiz bearbeiten", style=discord.ButtonStyle.secondary, row=0, custom_id="note_action")
    async def note_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit player notes"""
        modal = NoteModal(self.cog, self.player, self.parent_view)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔙 Zurück", style=discord.ButtonStyle.primary, row=1, custom_id="back_action")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to main view"""
        embed = self.parent_view.create_player_embed(self.player)
        await interaction.response.edit_message(
            embed=embed,
            view=self
        )


class ConfirmRemovalView(discord.ui.View):
    """Confirmation view for player removal"""
    
    def __init__(self, cog, player: dict, parent_view: PlayerAccessView):
        super().__init__(timeout=60.0)
        self.cog = cog
        self.player = player
        self.parent_view = parent_view
    
    @discord.ui.button(label="✅ Ja, entfernen", style=discord.ButtonStyle.danger, row=0)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm removal"""
        success, message = await self.cog.remove_from_whitelist(
            interaction,
            self.player,
            "Manuelle Entfernung durch Admin"
        )
        
        embed = discord.Embed(
            title="✅ Erfolgreich" if success else "❌ Fehler",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )
        
        if success:
            # Refresh parent view
            await self.cog.refresh_player_list(interaction, self.parent_view)
            self.parent_view.update_select_options()
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="❌ Abbrechen", style=discord.ButtonStyle.secondary, row=0)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel removal"""
        action_view = PlayerActionView(self.cog, self.player, self.parent_view)
        embed = self.parent_view.create_player_embed(self.player)
        await interaction.response.edit_message(embed=embed, view=action_view)


class WhitelistModal(discord.ui.Modal):
    """Modal for confirming whitelist action with extended options"""
    
    def __init__(self, cog, player: dict, view: PlayerAccessView):
        super().__init__(title="🎮 Spieler whitelisten", timeout=300.0)
        self.cog = cog
        self.player = player
        self.view = view
        
        self.reason = discord.ui.TextInput(
            label="Grund für die Whitelist",
            style=discord.TextStyle.paragraph,
            placeholder="Warum soll dieser Spieler gewhitelisted werden?",
            required=True,
            max_length=500,
            default="Manuelle Whitelist durch Admin"
        )
        self.add_item(self.reason)
        
        self.priority = discord.ui.TextInput(
            label="Priorität (0-5, optional)",
            style=discord.TextStyle.short,
            placeholder="0 (Standard) bis 5 (VIP)",
            required=False,
            default="0"
        )
        self.add_item(self.priority)
        
        self.notes = discord.ui.TextInput(
            label="Interne Notizen (optional)",
            style=discord.TextStyle.paragraph,
            placeholder="Zusätzliche Informationen...",
            required=False,
            max_length=1000
        )
        self.add_item(self.notes)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        # Validate priority
        try:
            priority = int(self.priority.value) if self.priority.value else 0
            if not 0 <= priority <= 5:
                raise ValueError("Priority must be between 0 and 5")
        except ValueError:
            await interaction.followup.send(
                "❌ Ungültige Priorität! Bitte eine Zahl zwischen 0 und 5 eingeben.",
                ephemeral=True
            )
            return
        
        success, message = await self.cog.whitelist_player(
            interaction,
            self.player,
            self.reason.value,
            priority,
            self.notes.value if self.notes.value else None
        )
        
        if success:
            # Refresh the view to show updated status
            await self.cog.refresh_player_list(interaction, self.view)
            self.view.update_select_options()
            
            embed = discord.Embed(
                title="✅ Erfolgreich",
                description=message,
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                f"❌ {message}",
                ephemeral=True
            )


class NoteModal(discord.ui.Modal):
    """Modal for editing player notes"""
    
    def __init__(self, cog, player: dict, view: PlayerAccessView):
        super().__init__(title="📝 Notizen bearbeiten", timeout=300.0)
        self.cog = cog
        self.player = player
        self.view = view
        
        existing_notes = player.get("notes", "")
        
        self.notes_input = discord.ui.TextInput(
            label="Notizen",
            style=discord.TextStyle.paragraph,
            placeholder="Interne Notizen zu diesem Spieler...",
            required=False,
            default=existing_notes,
            max_length=1000
        )
        self.add_item(self.notes_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        success, message = await self.cog.update_player_notes(
            interaction,
            self.player,
            self.notes_input.value
        )
        
        embed = discord.Embed(
            title="✅ Erfolgreich" if success else "❌ Fehler",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )
        
        if success:
            await self.cog.refresh_player_list(interaction, self.view)
            self.view.update_select_options()
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class PlayerAccessCog(commands.Cog):
    """
    Advanced Player Access Control System
    
    Ein umfassendes System zur Verwaltung von Spieler-Zugängen
    mit interaktiven Menüs, Rollenzuweisung, Prioritäten und Logging.
    
    Befehle:
    - [p]playeraccess - Hauptmenü öffnen
    - [p]pa - Kurzform
    - [p]access - Alternative
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=847362918473629, force_registration=True)
        
        default_guild = {
            "access_role": None,
            "whitelisted_players": {},
            "admin_roles": [],
            "log_channel": None,
            "auto_remove_inactive": False,
            "inactive_days": 30,
            "max_priority_slots": {"5": 5, "4": 10, "3": 20},  # Max players per priority level
            "welcome_message": True,
            "dm_on_whitelist": True
        }
        self.config.register_guild(**default_guild)
        
        # Cache for external player data
        self._player_cache = {}
        self._cache_expiry = {}
    
    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to use access commands"""
        # Check for admin roles
        admin_roles = await self.config.guild(interaction.guild).admin_roles()
        if admin_roles:
            user_roles = [role.id for role in interaction.user.roles]
            if any(role_id in user_roles for role_id in admin_roles):
                return True
        
        # Check for server admin/owner
        if interaction.user.guild_permissions.administrator or interaction.user == interaction.guild.owner():
            return True
        
        return False
    
    async def log_action(self, guild: discord.Guild, action: str, user: discord.Member, details: str, color: discord.Color = None):
        """Log access actions to configured channel"""
        log_channel_id = await self.config.guild(guild).log_channel()
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="📋 Access Log",
                    description=f"**Aktion:** {action}",
                    color=color or discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(name="👤 Durchgeführt von", value=f"{user.mention} (`{user.id}`)", inline=False)
                embed.add_field(name="📝 Details", value=details, inline=False)
                embed.set_footer(text=f"Guild: {guild.name} | ID: {guild.id}")
                
                try:
                    await log_channel.send(embed=embed)
                except discord.Forbidden:
                    pass
    
    async def refresh_player_list(self, interaction: discord.Interaction, view: PlayerAccessView):
        """Refresh the player list from cache or external source"""
        # In production, fetch from your game server API
        # For now, load from config and add example data
        whitelisted_data = await self.config.guild(interaction.guild).whitelisted_players()
        
        players = []
        for player_id, player_data in whitelisted_data.items():
            players.append({
                "id": int(player_id),
                "name": player_data.get("name", "Unbekannt"),
                "whitelisted": True,
                "priority": player_data.get("priority", 0),
                "role": player_data.get("role_name", "Keine"),
                "added_by": player_data.get("added_by", "Unbekannt"),
                "reason": player_data.get("reason", "Kein Grund angegeben"),
                "timestamp": player_data.get("timestamp", 0),
                "notes": player_data.get("notes", ""),
                "last_seen": player_data.get("last_seen", 0)
            })
        
        # Add example pending players if list is empty (for demo)
        if not players:
            players = [
                {"id": i, "name": f"Spieler_{i:03d}", "whitelisted": i % 3 == 0, "priority": i % 6}
                for i in range(1, 26)
            ]
        
        view.players = players
        view.current_page = 0
        view.update_select_options()
        
        # Show feedback
        feedback = discord.Embed(
            title="🔄 Aktualisiert",
            description=f"{len(players)} Spieler geladen",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=feedback, ephemeral=True)
    
    async def whitelist_player(self, interaction: discord.Interaction, player: dict, reason: str, priority: int = 0, notes: str = None) -> tuple:
        """Add a player to the whitelist and assign role"""
        guild = interaction.guild
        member = interaction.user
        
        # Check priority limits
        max_slots = await self.config.guild(guild).max_priority_slots()
        priority_str = str(priority)
        if priority_str in max_slots:
            current_count = sum(1 for p in await self.config.guild(guild).whitelisted_players() 
                              if await self.config.guild(guild).whitelisted_players()[p].get("priority", 0) == priority)
            if current_count >= max_slots[priority_str]:
                return False, f"Maximale Anzahl an Spielern mit Priorität {priority} erreicht!"
        
        # Get configured role
        role_id = await self.config.guild(guild).access_role()
        role = guild.get_role(role_id) if role_id else None
        
        # Try to find Discord member
        target_member = None
        try:
            # Search by name
            target_member = discord.utils.get(guild.members, name=player["name"])
            if not target_member:
                # Search by nickname
                target_member = discord.utils.get(guild.members, nick=player["name"])
        except:
            pass
        
        try:
            if target_member and role:
                await target_member.add_roles(role, reason=reason[:500])
                
                # Save to config
                async with self.config.guild(guild).whitelisted_players() as players:
                    players[str(player["id"])] = {
                        "name": player["name"],
                        "discord_id": target_member.id,
                        "role_name": role.name,
                        "added_by": member.id,
                        "reason": reason,
                        "priority": priority,
                        "notes": notes or "",
                        "timestamp": int(datetime.utcnow().timestamp()),
                        "last_seen": int(datetime.utcnow().timestamp())
                    }
                
                # Log action
                await self.log_action(
                    guild,
                    "Spieler gewhitelisted",
                    member,
                    f"Spieler: {player['name']} ({target_member.mention})\nGrund: {reason}\nPriorität: {'⭐' * priority}",
                    discord.Color.green()
                )
                
                # Send DM if enabled
                if await self.config.guild(guild).dm_on_whitelist():
                    try:
                        dm_embed = discord.Embed(
                            title="🎉 Willkommen!",
                            description=f"Du wurdest von **{member.display_name}** zur Whitelist hinzugefügt!\n\n**Grund:** {reason}",
                            color=discord.Color.green()
                        )
                        dm_embed.add_field(name="📋 Deine Rolle", value=f"{role.name}", inline=False)
                        await target_member.send(embed=dm_embed)
                    except discord.Forbidden:
                        pass
                
                # Send welcome message if enabled
                if await self.config.guild(guild).welcome_message():
                    channel = interaction.channel
                    welcome_embed = discord.Embed(
                        title="🎉 Neuer gewhitelisted Spieler!",
                        description=f"Willkommen **{player['name']}**!",
                        color=discord.Color.green()
                    )
                    welcome_embed.add_field(name="Moderator", value=member.mention, inline=True)
                    welcome_embed.add_field(name="Priorität", value="⭐" * priority, inline=True)
                    await channel.send(embed=welcome_embed)
                
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
                        "priority": priority,
                        "notes": notes or "",
                        "timestamp": int(datetime.utcnow().timestamp()),
                        "last_seen": 0
                    }
                
                await self.log_action(
                    guild,
                    "Spieler zur Whitelist hinzugefügt",
                    member,
                    f"Spieler: {player['name']}\nGrund: {reason}\nPriorität: {priority}\n(Hinweis: Keine Rollenzuweisung möglich)",
                    discord.Color.orange()
                )
                
                return True, f"Spieler **{player['name']}** wurde zur Whitelist hinzugefügt! (Rolle konnte nicht zugewiesen werden)"
                
        except Exception as e:
            return False, f"Fehler beim Whitelisten: {str(e)}"
    
    async def remove_from_whitelist(self, interaction: discord.Interaction, player: dict, reason: str) -> tuple:
        """Remove a player from the whitelist"""
        guild = interaction.guild
        member = interaction.user
        
        try:
            # Find Discord member
            target_member = discord.utils.get(guild.members, name=player["name"])
            
            # Remove role if exists
            role_id = await self.config.guild(guild).access_role()
            role = guild.get_role(role_id) if role_id else None
            
            if target_member and role:
                await target_member.remove_roles(role, reason=reason[:500])
            
            # Remove from config
            async with self.config.guild(guild).whitelisted_players() as players:
                if str(player["id"]) in players:
                    del players[str(player["id"])]
            
            # Log action
            await self.log_action(
                guild,
                "Spieler entfernt",
                member,
                f"Spieler: {player['name']}\nGrund: {reason}",
                discord.Color.red()
            )
            
            return True, f"Spieler **{player['name']}** wurde erfolgreich von der Whitelist entfernt!"
            
        except Exception as e:
            return False, f"Fehler beim Entfernen: {str(e)}"
    
    async def update_player_notes(self, interaction: discord.Interaction, player: dict, notes: str) -> tuple:
        """Update player notes"""
        guild = interaction.guild
        
        try:
            async with self.config.guild(guild).whitelisted_players() as players:
                if str(player["id"]) in players:
                    players[str(player["id"])]["notes"] = notes
                else:
                    return False, "Spieler nicht gefunden!"
            
            await self.log_action(
                guild,
                "Notizen aktualisiert",
                interaction.user,
                f"Spieler: {player['name']}\nNotizen: {notes[:100]}...",
                discord.Color.blue()
            )
            
            return True, "Notizen erfolgreich aktualisiert!"
            
        except Exception as e:
            return False, f"Fehler: {str(e)}"
    
    async def show_statistics(self, interaction: discord.Interaction, players: List[dict]):
        """Show detailed statistics"""
        total = len(players)
        whitelisted = sum(1 for p in players if p.get("whitelisted", False))
        pending = total - whitelisted
        
        # Priority distribution
        priority_dist = {}
        for p in players:
            prio = p.get("priority", 0)
            priority_dist[prio] = priority_dist.get(prio, 0) + 1
        
        # Recent additions (last 7 days)
        seven_days_ago = int((datetime.utcnow() - timedelta(days=7)).timestamp())
        recent = sum(1 for p in players if p.get("timestamp", 0) > seven_days_ago)
        
        embed = discord.Embed(
            title="📊 Zugriffs-Statistiken",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="📈 Übersicht",
            value=f"**Gesamt:** {total}\n**Gewhitelisted:** {whitelisted} ✅\n**Ausstehend:** {pending} ⏳",
            inline=True
        )
        
        embed.add_field(
            name="🆕 Zuletzt",
            value=f"**Letzte 7 Tage:** {recent}",
            inline=True
        )
        
        embed.add_field(
            name="⭐ Prioritäten",
            value="\n".join([f"Priorität {p}: {c}" for p, c in sorted(priority_dist.items())]) or "Keine",
            inline=False
        )
        
        # Top contributors
        added_by_count = {}
        for p in players:
            if p.get("whitelisted"):
                added_by = p.get("added_by", 0)
                added_by_count[added_by] = added_by_count.get(added_by, 0) + 1
        
        top_contributors = sorted(added_by_count.items(), key=lambda x: x[1], reverse=True)[:5]
        if top_contributors:
            contrib_text = "\n".join([f"<@{uid}>: {count}" for uid, count in top_contributors])
            embed.add_field(
                name="🏆 Top Moderatoren",
                value=contrib_text,
                inline=False
            )
        
        embed.set_footer(text=f"Server: {interaction.guild.name}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.group(name="playeraccess", aliases=["pa", "access"], invoke_without_command=True)
    @commands.guild_only()
    async def playeraccess_group(self, ctx: commands.Context):
        """
        🎮 Player Access Control System
        
        Verwalte Spieler-Zugänge mit modernen Interaktionsmöglichkeiten.
        Nutze das Dropdown-Menü zur einfachen Verwaltung.
        """
        # Check permissions
        if not await self.check_permissions(type('obj', (object,), {'user': ctx.author, 'guild': ctx.guild, 'permissions': ctx.author.guild_permissions})()):
            await ctx.send("❌ Du hast keine Berechtigung, diesen Befehl zu verwenden!")
            return
        
        # Load players
        whitelisted_data = await self.config.guild(ctx.guild).whitelisted_players()
        players = []
        
        for player_id, player_data in whitelisted_data.items():
            players.append({
                "id": int(player_id),
                "name": player_data.get("name", "Unbekannt"),
                "whitelisted": True,
                "priority": player_data.get("priority", 0),
                "role": player_data.get("role_name", "Keine"),
                "added_by": player_data.get("added_by", "Unbekannt"),
                "reason": player_data.get("reason", "Kein Grund"),
                "timestamp": player_data.get("timestamp", 0),
                "notes": player_data.get("notes", "")
            })
        
        # Add example players if none exist
        if not players:
            players = [
                {"id": i, "name": f"Spieler_{i:03d}", "whitelisted": i % 3 == 0, "priority": i % 6}
                for i in range(1, 26)
            ]
        
        # Create main embed
        embed = discord.Embed(
            title="🎮 Player Access Control",
            description="""
            Willkommen im Player Access Management System!
            
            Wähle einen Spieler aus dem Dropdown-Menü und verwalte dessen Zugang.
            
            **Funktionen:**
            🔍 Suche nach Spielern
            ✅ Whitelist mit Rollenzuweisung
            ⭐ Prioritätssystem (0-5)
            📝 Interne Notizen
            📊 Detaillierte Statistiken
            📋 Umfassendes Logging
            """,
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="📊 Aktueller Status",
            value=f"**Gesamt:** {len(players)}\n**Gewhitelisted:** {sum(1 for p in players if p.get('whitelisted'))}\n**Ausstehend:** {sum(1 for p in players if not p.get('whitelisted'))}",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Konfiguration",
            value=f"**Zugangsrolle:** {'Konfiguriert' if await self.config.guild(ctx.guild).access_role() else 'Nicht konfiguriert'}\n**Admin-Rollen:** {len(await self.config.guild(ctx.guild).admin_roles())}",
            inline=False
        )
        
        embed.set_footer(text=f"Angefragt von {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        view = PlayerAccessView(self, players)
        
        message = await ctx.send(embed=embed, view=view)
        
        # Store message reference for views that need it
        view.message = message
    
    @playeraccess_group.command(name="config")
    @commands.admin_or_permissions(administrator=True)
    async def config_command(self, ctx: commands.Context):
        """
        Konfiguration des Access Systems anzeigen
        """
        guild = ctx.guild
        config = self.config.guild(guild)
        
        access_role_id = await config.access_role()
        access_role = guild.get_role(access_role_id) if access_role_id else None
        
        admin_role_ids = await config.admin_roles()
        admin_roles = [guild.get_role(rid) for rid in admin_role_ids if guild.get_role(rid)]
        
        log_channel_id = await config.log_channel()
        log_channel = guild.get_channel(log_channel_id) if log_channel_id else None
        
        embed = discord.Embed(
            title="⚙️ Access System Konfiguration",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="🎭 Rollen",
            value=f"**Zugangsrolle:** {access_role.mention if access_role else 'Nicht konfiguriert'}\n**Admin-Rollen:** {', '.join([r.mention for r in admin_roles]) if admin_roles else 'Server-Administratoren'}",
            inline=False
        )
        
        embed.add_field(
            name="📋 Logging",
            value=f"**Log-Kanal:** {log_channel.mention if log_channel else 'Nicht konfiguriert'}",
            inline=False
        )
        
        max_slots = await config.max_priority_slots()
        slots_text = "\n".join([f"Priorität {p}: {max} Slots" for p, max in max_slots.items()])
        embed.add_field(
            name="⭐ Prioritäts-Limits",
            value=slots_text,
            inline=False
        )
        
        embed.add_field(
            name="🔔 Benachrichtigungen",
            value=f"**DM bei Whitelist:** {'Aktiviert' if await config.dm_on_whitelist() else 'Deaktiviert'}\n**Willkommensnachricht:** {'Aktiviert' if await config.welcome_message() else 'Deaktiviert'}",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @playeraccess_group.command(name="setrole")
    @commands.admin_or_permissions(administrator=True)
    async def set_access_role(self, ctx: commands.Context, role: discord.Role):
        """
        Die Rolle festlegen, die gewhitelisted Spieler erhalten
        """
        await self.config.guild(ctx.guild).access_role.set(role.id)
        
        embed = discord.Embed(
            title="✅ Rolle konfiguriert",
            description=f"Die Zugangsrolle wurde auf **{role.name}** gesetzt.\n\nSpieler, die ab jetzt gewhitelisted werden, erhalten automatisch diese Rolle.",
            color=discord.Color.green()
        )
        
        await self.log_action(
            ctx.guild,
            "Zugangsrolle geändert",
            ctx.author,
            f"Neue Rolle: {role.name} ({role.id})",
            discord.Color.blue()
        )
        
        await ctx.send(embed=embed)
    
    @playeraccess_group.command(name="addadminrole")
    @commands.admin_or_permissions(administrator=True)
    async def add_admin_role(self, ctx: commands.Context, role: discord.Role):
        """
        Eine Admin-Rolle hinzufügen, die das Menü verwenden darf
        """
        async with self.config.guild(ctx.guild).admin_roles() as admin_roles:
            if role.id not in admin_roles:
                admin_roles.append(role.id)
        
        embed = discord.Embed(
            title="✅ Admin-Rolle hinzugefügt",
            description=f"**{role.name}** kann nun das Access-System verwenden.",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    @playeraccess_group.command(name="removeadminrole")
    @commands.admin_or_permissions(administrator=True)
    async def remove_admin_role(self, ctx: commands.Context, role: discord.Role):
        """
        Eine Admin-Rolle entfernen
        """
        async with self.config.guild(ctx.guild).admin_roles() as admin_roles:
            if role.id in admin_roles:
                admin_roles.remove(role.id)
        
        embed = discord.Embed(
            title="✅ Admin-Rolle entfernt",
            description=f"**{role.name}** hat keinen Zugriff mehr auf das Access-System.",
            color=discord.Color.orange()
        )
        
        await ctx.send(embed=embed)
    
    @playeraccess_group.command(name="setlogchannel")
    @commands.admin_or_permissions(administrator=True)
    async def set_log_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """
        Den Log-Kanal für Access-Aktionen festlegen
        """
        await self.config.guild(ctx.guild).log_channel.set(channel.id)
        
        embed = discord.Embed(
            title="✅ Log-Kanal konfiguriert",
            description=f"Alle Access-Aktionen werden nun in {channel.mention} protokolliert.",
            color=discord.Color.green()
        )
        
        # Send test log
        await self.log_action(
            ctx.guild,
            "Log-Kanal eingerichtet",
            ctx.author,
            "Der Log-Kanal wurde erfolgreich konfiguriert.",
            discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    @playeraccess_group.command(name="disablelogs")
    @commands.admin_or_permissions(administrator=True)
    async def disable_logs(self, ctx: commands.Context):
        """
        Logging deaktivieren
        """
        await self.config.guild(ctx.guild).log_channel.set(None)
        
        embed = discord.Embed(
            title="✅ Logging deaktiviert",
            description="Es werden keine Access-Aktionen mehr protokolliert.",
            color=discord.Color.orange()
        )
        
        await ctx.send(embed=embed)
    
    @playeraccess_group.command(name="stats")
    async def show_stats(self, ctx: commands.Context):
        """
        Zeige detaillierte Statistiken über das Access System
        """
        if not await self.check_permissions(type('obj', (object,), {'user': ctx.author, 'guild': ctx.guild, 'permissions': ctx.author.guild_permissions})()):
            await ctx.send("❌ Du hast keine Berechtigung, diesen Befehl zu verwenden!")
            return
        
        # Load players
        whitelisted_data = await self.config.guild(ctx.guild).whitelisted_players()
        players = []
        
        for player_id, player_data in whitelisted_data.items():
            players.append({
                "id": int(player_id),
                "name": player_data.get("name", "Unbekannt"),
                "whitelisted": True,
                "priority": player_data.get("priority", 0),
                "timestamp": player_data.get("timestamp", 0),
                "added_by": player_data.get("added_by", 0)
            })
        
        await self.show_statistics(
            type('obj', (object,), {'response': type('obj', (object,), {'send_message': lambda **kw: ctx.send(**kw)})(), 'guild': ctx.guild})(),
            players
        )
    
    @playeraccess_group.command(name="export")
    @commands.admin_or_permissions(administrator=True)
    async def export_whitelist(self, ctx: commands.Context):
        """
        Exportiere die Whitelist als Textdatei
        """
        whitelisted_data = await self.config.guild(ctx.guild).whitelisted_players()
        
        if not whitelisted_data:
            await ctx.send("❌ Keine gewhitelisted Spieler zum Exportieren vorhanden!")
            return
        
        export_text = "=== PLAYER WHITELIST EXPORT ===\n\n"
        export_text += f"Server: {ctx.guild.name}\n"
        export_text += f"Datum: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
        export_text += f"Gesamt: {len(whitelisted_data)} Spieler\n\n"
        export_text += "=" * 40 + "\n\n"
        
        for player_id, data in sorted(whitelisted_data.items(), key=lambda x: x[1].get("timestamp", 0), reverse=True):
            export_text += f"ID: {player_id}\n"
            export_text += f"Name: {data.get('name', 'Unbekannt')}\n"
            export_text += f"Status: {'Gewhitelisted' if data.get('whitelisted', False) else 'Ausstehend'}\n"
            export_text += f"Priorität: {'⭐' * data.get('priority', 0)} ({data.get('priority', 0)})\n"
            export_text += f"Hinzugefügt von: {data.get('added_by', 'Unbekannt')}\n"
            export_text += f"Grund: {data.get('reason', 'Kein Grund')}\n"
            if data.get("notes"):
                export_text += f"Notizen: {data.get('notes')}\n"
            export_text += "-" * 40 + "\n"
        
        # Create file
        filename = f"whitelist_export_{ctx.guild.id}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(export_text)
        
        await ctx.send(
            "✅ Whitelist erfolgreich exportiert!",
            file=discord.File(filename)
        )
        
        # Clean up
        import os
        os.remove(filename)
    
    @playeraccess_group.command(name="cleanup")
    @commands.admin_or_permissions(administrator=True)
    async def cleanup_inactive(self, ctx: commands.Context, days: int = 30):
        """
        Inaktive Spieler von der Whitelist entfernen
        
        days: Anzahl der Tage der Inaktivität (Standard: 30)
        """
        if days < 1 or days > 365:
            await ctx.send("❌ Bitte gib eine gültige Anzahl an Tagen an (1-365)!")
            return
        
        whitelisted_data = await self.config.guild(ctx.guild).whitelisted_players()
        cutoff_time = int((datetime.utcnow() - timedelta(days=days)).timestamp())
        
        removed_count = 0
        removed_players = []
        
        async with self.config.guild(ctx.guild).whitelisted_players() as players:
            to_remove = []
            for player_id, data in players.items():
                last_seen = data.get("last_seen", data.get("timestamp", 0))
                if last_seen < cutoff_time:
                    to_remove.append(player_id)
                    removed_players.append(data.get("name", "Unbekannt"))
            
            for player_id in to_remove:
                del players[player_id]
                removed_count += 1
        
        if removed_count == 0:
            await ctx.send(f"✅ Keine inaktiven Spieler gefunden (letzte Aktivität vor mehr als {days} Tagen).")
        else:
            embed = discord.Embed(
                title="✅ Cleanup abgeschlossen",
                description=f"{removed_count} inaktive Spieler wurden von der Whitelist entfernt.\n\n**Entfernte Spieler:**\n{', '.join(removed_players[:10])}{'...' if len(removed_players) > 10 else ''}",
                color=discord.Color.orange()
            )
            
            await self.log_action(
                ctx.guild,
                "Inaktive Spieler entfernt",
                ctx.author,
                f"{removed_count} Spieler entfernt (Inaktivität: {days}+ Tage)",
                discord.Color.orange()
            )
            
            await ctx.send(embed=embed)


def setup(bot):
    """Load the cog"""
    bot.add_cog(PlayerAccessCog(bot))
