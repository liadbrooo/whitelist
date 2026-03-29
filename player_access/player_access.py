"""
Player Access Control - Ein einfacher Whitelist-Cog für RedBot
Installation:
1. [p]cog installpath /workspace/player_access
2. [p]load player_access
3. [p]pa setrole @Rolle
Fertig!

Befehle:
- [p]pa menu - Öffnet das Dropdown-Menü zum Whitelisten
- [p]pa setrole @Rolle - Setzt die Whitelist-Rolle (einmalig)
- [p]pa remove <Spieler> - Entfernt Spieler von der Whitelist
- [p]pa list - Zeigt alle gewhitelisteten Spieler
- [p]pa admins - Zeigt Admins die diesen Cog nutzen dürfen
"""

import discord
from discord.ext import commands
from redbot.core import Config, checks
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate
import asyncio

class PlayerAccess(commands.Cog):
    """Einfache Spieler-Whitelist mit Dropdown-Menü"""
    
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7845123690, force_registration=True)
        
        default_guild = {
            "whitelist_role": None,
            "admin_roles": [],
            "whitelisted_players": {}
        }
        self.config.register_guild(**default_guild)
    
    async def is_admin(self, ctx):
        """Prüft ob User Admin-Rechte hat"""
        guild = ctx.guild
        if await self.bot.is_owner(ctx.author):
            return True
        
        admin_roles = await self.config.guild(guild).admin_roles()
        user_roles = [role.id for role in ctx.author.roles]
        
        return any(role_id in user_roles for role_id in admin_roles)
    
    @commands.group(name="playeraccess", aliases=["pa", "access"])
    @commands.guild_only()
    async def pa_group(self, ctx):
        """Player Access Control Hauptbefehl"""
        pass
    
    @pa_group.command(name="setrole")
    async def pa_setrole(self, ctx, role: discord.Role):
        """Setzt die Rolle die Spieler bei Whitelist erhalten"""
        async with self.config.guild(ctx.guild).whitelist_role() as current:
            if current:
                old_role = ctx.guild.get_role(current)
                old_name = old_role.name if old_role else "Unbekannt"
                await ctx.send(f"✅ Whitelist-Rolle geändert von `{old_name}` zu `{role.name}`")
            else:
                await ctx.send(f"✅ Whitelist-Rolle gesetzt: `{role.name}`")
        
        await self.config.guild(ctx.guild).whitelist_role.set(role.id)
    
    @pa_group.command(name="addadmin")
    async def pa_addadmin(self, ctx, role: discord.Role):
        """Fügt eine Admin-Rolle hinzu (darf pa-Befehle nutzen)"""
        async with self.config.guild(ctx.guild).admin_roles() as admins:
            if role.id not in admins:
                admins.append(role.id)
                await ctx.send(f"✅ `{role.name}` kann jetzt den Player-Access-Cog verwalten")
            else:
                await ctx.send(f"⚠️ `{role.name}` ist bereits Admin")
    
    @pa_group.command(name="removeadmin")
    async def pa_removeadmin(self, ctx, role: discord.Role):
        """Entfernt eine Admin-Rolle"""
        async with self.config.guild(ctx.guild).admin_roles() as admins:
            if role.id in admins:
                admins.remove(role.id)
                await ctx.send(f"✅ `{role.name}` ist kein Admin mehr")
            else:
                await ctx.send(f"⚠️ `{role.name}` war kein Admin")
    
    @pa_group.command(name="admins")
    async def pa_admins(self, ctx):
        """Zeigt alle Admin-Rollen"""
        admin_ids = await self.config.guild(ctx.guild).admin_roles()
        if not admin_ids:
            await ctx.send("❌ Keine Admin-Rollen konfiguriert")
            return
        
        admin_names = []
        for rid in admin_ids:
            role = ctx.guild.get_role(rid)
            if role:
                admin_names.append(f"`{role.name}`")
        
        await ctx.send(f"👑 Admin-Rollen: {', '.join(admin_names)}")
    
    @pa_group.command(name="menu")
    async def pa_menu(self, ctx):
        """Öffnet das Whitelist-Menü mit Dropdown"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Du hast keine Berechtigung dafür")
            return
        
        role_id = await self.config.guild(ctx.guild).whitelist_role()
        if not role_id:
            await ctx.send("❌ Erst setze eine Rolle mit `pa setrole @Rolle`")
            return
        
        whitelist_data = await self.config.guild(ctx.guild).whitelisted_players()
        
        embed = discord.Embed(
            title="🎮 Spieler Whitelist",
            description="Wähle einen Spieler aus dem Dropdown um ihn zu whitelisten.\n\n**Aktuell gewhitelistet:**",
            color=discord.Color.green()
        )
        
        if whitelist_data:
            players_list = "\n".join([f"• {name}" for name in whitelist_data.keys()])
            embed.add_field(name=f"({len(whitelist_data)} Spieler)", value=players_list[:1024], inline=False)
        else:
            embed.add_field(name="Keine Spieler", value="Nutze das Dropdown um Spieler hinzuzufügen", inline=False)
        
        embed.set_footer(text="Dropdown unten verwenden ⬇️")
        
        view = PlayerSelectView(self, ctx.guild)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()
        
        if view.player_selected:
            embed.description = f"✅ **{view.player_selected}** wurde zur Whitelist hinzugefügt!"
            embed.set_footer(text=f"Von: {ctx.author.name}")
            await msg.edit(embed=embed, view=None)
    
    @pa_group.command(name="remove")
    async def pa_remove(self, ctx, player_name: str):
        """Entfernt einen Spieler von der Whitelist"""
        if not await self.is_admin(ctx):
            await ctx.send("❌ Du hast keine Berechtigung dafür")
            return
        
        async with self.config.guild(ctx.guild).whitelisted_players() as players:
            if player_name in players:
                del players[player_name]
                
                role_id = await self.config.guild(ctx.guild).whitelist_role()
                if role_id:
                    role = ctx.guild.get_role(role_id)
                    if role:
                        for member in ctx.guild.members:
                            if member.display_name.lower() == player_name.lower():
                                await member.remove_roles(role, reason=f"Von Whitelist entfernt durch {ctx.author.name}")
                
                await ctx.send(f"✅ **{player_name}** wurde von der Whitelist entfernt")
            else:
                await ctx.send(f"❌ **{player_name}** ist nicht auf der Whitelist")
    
    @pa_group.command(name="list")
    async def pa_list(self, ctx):
        """Zeigt alle gewhitelisteten Spieler"""
        players = await self.config.guild(ctx.guild).whitelisted_players()
        
        if not players:
            await ctx.send("📋 Die Whitelist ist leer")
            return
        
        embed = discord.Embed(
            title="📋 Gewhitelistete Spieler",
            description=f"Insgesamt: **{len(players)}**",
            color=discord.Color.blue()
        )
        
        players_text = "\n".join([f"• {name}" for name in sorted(players.keys())])
        
        if len(players_text) > 4096:
            players_text = players_text[:4093] + "..."
        
        embed.add_field(name="Spieler", value=players_text, inline=False)
        embed.set_footer(text=f"Abruf von: {ctx.author.name}")
        
        await ctx.send(embed=embed)


class PlayerSelect(discord.ui.Select):
    """Dropdown zur Spielerauswahl"""
    
    def __init__(self, cog, guild):
        self.cog = cog
        self.guild = guild
        self.all_members = [m for m in guild.members if not m.bot]
        
        options = []
        for member in self.all_members[:25]:
            emoji = "✅" if member.guild_permissions.administrator else "👤"
            options.append(discord.SelectOption(
                label=member.display_name[:100],
                value=str(member.id),
                emoji=emoji,
                description=f"ID: {member.id}"[:100]
            ))
        
        super().__init__(
            placeholder="Wähle einen Spieler...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_id = int(self.values[0])
        member = self.guild.get_member(selected_id)
        
        if not member:
            await interaction.response.send_message("❌ Spieler nicht gefunden", ephemeral=True)
            return
        
        async with self.cog.config.guild(self.guild).whitelisted_players() as players:
            players[member.display_name] = {
                "id": member.id,
                "added_by": interaction.user.id,
                "timestamp": int(interaction.created_at.timestamp())
            }
        
        role_id = await self.cog.config.guild(self.guild).whitelist_role()
        if role_id:
            role = self.guild.get_role(role_id)
            if role and role not in member.roles:
                await member.add_roles(role, reason=f"Durch {interaction.user.name} gewhitelistet")
        
        await interaction.response.send_message(
            f"✅ **{member.display_name}** wurde erfolgreich gewhitelistet!",
            ephemeral=True
        )


class PlayerSelectView(discord.ui.View):
    """View mit dem Player-Select-Dropdown"""
    
    def __init__(self, cog, guild):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.player_selected = None
        self.add_item(PlayerSelect(cog, guild))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.cog.is_admin(type('FakeCtx', (), {'author': interaction.user, 'guild': self.guild})())


async def setup(bot):
    """Lädt den Cog"""
    await bot.add_cog(PlayerAccess(bot))
