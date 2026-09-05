import discord
from discord.ext import commands
import random
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# ==========================================
# FLASK WEB SUNUCUSU (7/24 Aktif Kalması İçin)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Ruthless League Bot Aktif!"

def run():
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ==========================================
# OTOMATİK PİNG (UYUMAMAK İÇİN)
# ==========================================
DEPLOYED_URL = os.environ.get('DEPLOYED_URL', '')

def self_ping():
    while True:
        time.sleep(240)  # 4 dakikada bir
        if not DEPLOYED_URL:
            continue
        try:
            urllib.request.urlopen(DEPLOYED_URL, timeout=10)
        except Exception:
            pass  # Hata olursa sessizce devam et

def start_ping():
    t = Thread(target=self_ping, daemon=True)
    t.start()

# ==========================================
# BOT VE INTENTS AYARLARI
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Üye yönetimi ve isim/rol değiştirme için zorunlu

bot = commands.Bot(command_prefix=".", intents=intents)

# Veri dosyasının bulunduğu dizin
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERI_DOSYASI = os.path.join(BASE_DIR, "futbolcu_verileri.json")

def verileri_yukle():
    if os.path.exists(VERI_DOSYASI):
        with open(VERI_DOSYASI, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def verileri_kaydet(veri):
    with open(VERI_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=4)

oyuncular = verileri_yukle()

# ==========================================
# OTO ROL VERİSİ
# ==========================================
OTOROL_DOSYASI = os.path.join(BASE_DIR, "otorol_verisi.json")

def otorol_yukle():
    if os.path.exists(OTOROL_DOSYASI):
        with open(OTOROL_DOSYASI, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def otorol_kaydet(veri):
    with open(OTOROL_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=4)

otorol_veri = otorol_yukle()

# emoji_id (str) → rol_id (int)
OTOROL_HARITA = {
    "1527786179506733136": 1527786978928492676,   # top    → Maç
    "1527785963886088263": 1527787118833959012,   # kutu   → Çekiliş
    "1527785752971182171": 1527787281602187396,   # gazete → Haber
    "🏆":                  1527787371716804790,   # 🏆     → Lig
    "1527785588906791093": 1527787453560393769,   # takvim → Fikstür
}

# ==========================================
# OTO KAYIT — Sabit kullanıcı
# ==========================================
OTO_KAYIT_ID   = 1438202822897434738
OTO_KAYIT_ISIM = "V.Kompany | Bayern M."
OTO_KAYIT_MEVKI = "Teknik Direktör"

async def oto_kayit_yap(guild: discord.Guild):
    """Belirtilen kullanıcıyı sisteme Teknik D. olarak kaydeder (Discord rolleri/nick değiştirilmez)."""
    uid = str(OTO_KAYIT_ID)
    # Zaten kayıtlıysa tekrar işlem yapma
    if uid in oyuncular and oyuncular[uid].get("mevki") == OTO_KAYIT_MEVKI:
        return

    oyuncular[uid] = {
        "isim": OTO_KAYIT_ISIM,
        "mevki": OTO_KAYIT_MEVKI,
        "ant_ilerleme": 0,
        "son_ant_zamani": None,
        "penalti_golu": 0,
        "para": 100
    }
    verileri_kaydet(oyuncular)
    print(f"✅ Oto-kayıt (sistem): {OTO_KAYIT_ISIM} ({OTO_KAYIT_ID}) kaydedildi.")


@bot.event
async def on_ready():
    bot.add_view(TicketAcView())
    bot.add_view(TicketKapatView())
    print(f"⚽ {bot.user.name} Ruthless League için sahaya indi ve 7/24 aktif!")
    for guild in bot.guilds:
        await oto_kayit_yap(guild)


KAYIT_BILDIRIM_KANAL_ID = 1522571233353404436

@bot.event
async def on_member_join(member: discord.Member):
    if member.id == OTO_KAYIT_ID:
        await oto_kayit_yap(member.guild)

    # Kayıt Yetkilisi rolünü etiketle
    guild = member.guild
    kayit_yetkilisi_rol = discord.utils.get(guild.roles, name="Kayıt Yetkilisi")
    bildirim_kanal = guild.get_channel(KAYIT_BILDIRIM_KANAL_ID)
    if bildirim_kanal:
        rol_mention = kayit_yetkilisi_rol.mention if kayit_yetkilisi_rol else "@Kayıt Yetkilisi"
        embed = discord.Embed(
            title="👋 Yeni Üye Geldi!",
            description=(
                f"{member.mention} sunucuya katıldı.\n\n"
                f"Kayıt işlemi için lütfen ilgilenin."
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text="⚽ Ruthless League • Kayıt Sistemi")
        await bildirim_kanal.send(content=rol_mention, embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.content.strip().lower() == "sa":
        await message.reply("Aleyküm Selam Dostum Günün İyi Geçiyormu #🎽︱antrenman Yapmayı Unutma!")
    await bot.process_commands(message)

def _emoji_anahtar(emoji):
    """Emoji nesnesinden harita anahtarı döndürür."""
    if isinstance(emoji, str):
        return emoji          # 🏆 gibi unicode emoji
    return str(emoji.id)     # özel emoji → id string

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    msg_id = str(payload.message_id)
    if otorol_veri.get("mesaj_id") != msg_id:
        return
    anahtar = _emoji_anahtar(payload.emoji)
    rol_id = OTOROL_HARITA.get(anahtar)
    if not rol_id:
        return
    guild = bot.get_guild(payload.guild_id)
    uye = guild.get_member(payload.user_id)
    rol = guild.get_role(rol_id)
    if uye and rol:
        await uye.add_roles(rol)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == bot.user.id:
        return
    msg_id = str(payload.message_id)
    if otorol_veri.get("mesaj_id") != msg_id:
        return
    anahtar = _emoji_anahtar(payload.emoji)
    rol_id = OTOROL_HARITA.get(anahtar)
    if not rol_id:
        return
    guild = bot.get_guild(payload.guild_id)
    uye = guild.get_member(payload.user_id)
    rol = guild.get_role(rol_id)
    if uye and rol:
        await uye.remove_roles(rol)

def tac_mu(uye: discord.Member) -> bool:
    """Üyenin 'tac' rolü olup olmadığını kontrol eder."""
    return discord.utils.get(uye.roles, name="tac") is not None


def oyuncu_kontrol(user_id):
    varsayilan = {
        "isim": "Bilinmiyor",
        "mevki": "YOK",
        "ant_ilerleme": 0,
        "son_ant_zamani": None,
        "penalti_golu": 0,
        "para": 100
    }
    if str(user_id) not in oyuncular:
        oyuncular[str(user_id)] = varsayilan.copy()
    else:
        # Eksik alanları tamamla
        for alan, deger in varsayilan.items():
            if alan not in oyuncular[str(user_id)]:
                oyuncular[str(user_id)][alan] = deger
    verileri_kaydet(oyuncular)
    return oyuncular[str(user_id)]

# ==========================================
# TİCKET SİSTEMİ
# ==========================================

class TicketKapatView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Ticketı Kapat", style=discord.ButtonStyle.danger, custom_id="ticket_kapat")
    async def kapat(self, interaction: discord.Interaction, button: discord.ui.Button):
        kanal = interaction.channel
        embed = discord.Embed(
            title="🔒 Ticket Kapatılıyor",
            description="Bu ticket 5 saniye içinde silinecek...",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=5))
        await kanal.delete(reason="Ticket kapatıldı")


class TicketAcView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ticket Aç", style=discord.ButtonStyle.success, custom_id="ticket_ac")
    async def ticket_ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        uye = interaction.user

        # Aynı kişinin açık ticketı var mı kontrol et
        mevcut = discord.utils.get(guild.text_channels, name=f"ticket-{uye.name.lower()}")
        if mevcut:
            await interaction.response.send_message(
                f"❌ Zaten açık bir ticketın var: {mevcut.mention}", ephemeral=True
            )
            return

        # Kanal izinleri
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            uye: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True
            )
        }

        # Admin rollerine de erişim ver
        for rol in guild.roles:
            if rol.permissions.administrator:
                overwrites[rol] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        # Ticket kategorisi bul veya kanalsız oluştur
        kategori = discord.utils.get(guild.categories, name="🎫 Ticketlar")
        if not kategori:
            kategori = await guild.create_category("🎫 Ticketlar")

        kanal = await guild.create_text_channel(
            name=f"ticket-{uye.name}",
            overwrites=overwrites,
            category=kategori,
            reason=f"{uye.name} tarafından ticket açıldı"
        )

        embed = discord.Embed(
            title="🎫 Destek Talebi Oluşturuldu",
            description=(
                f"Merhaba {uye.mention}! 👋\n\n"
                f"Ticketın başarıyla oluşturuldu.\n"
                f"Sorununu veya talebini buraya yazabilirsin.\n"
                f"Bir yetkili en kısa sürede ilgilenecektir.\n\n"
                f"📌 İşin bittiğinde aşağıdaki butona basarak ticketı kapatabilirsin."
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="⚽ Ruthless League Destek Sistemi")
        await kanal.send(content=uye.mention, embed=embed, view=TicketKapatView())

        await interaction.response.send_message(
            f"✅ Ticketın oluşturuldu: {kanal.mention}", ephemeral=True
        )


@bot.command(name="tkur")
@commands.has_permissions(administrator=True)
async def ticket_kur(ctx):
    embed = discord.Embed(
        title="🎫 Ruthless League — Destek Merkezi",
        description=(
            "Herhangi bir konuda yardıma ihtiyaç duyuyor musun?\n\n"
            "📩 Aşağıdaki butona tıklayarak bir destek talebi oluşturabilirsin.\n"
            "Yetkililer en kısa sürede sana dönecektir.\n\n"
            "⚠️ Lütfen ticketları gereksiz yere açmayın."
        ),
        color=discord.Color.blurple()
    )
    embed.set_footer(text="⚽ Ruthless League Destek Sistemi")
    await ctx.send(embed=embed, view=TicketAcView())
    await ctx.message.delete()


# ==========================================
# KAYIT BUTON SİSTEMİ
# ==========================================
ROL_UYE       = 1522570902473019552
ROL_FUTBOLCU  = 1523967349932294234
ROL_TEKNIK_D  = 1522570884462809179

class KayitView(discord.ui.View):
    def __init__(self, uye: discord.Member, yeni_isim: str):
        super().__init__(timeout=60)
        self.uye = uye
        self.yeni_isim = yeni_isim
        self.tamamlandi = False

    async def rol_ver(self, interaction: discord.Interaction, rol_id: int, rol_adi: str):
        if self.tamamlandi:
            await interaction.response.send_message("❌ Bu kayıt zaten tamamlandı.", ephemeral=True)
            return
        self.tamamlandi = True
        for item in self.children:
            item.disabled = True

        try:
            await self.uye.edit(nick=self.yeni_isim)

            rol = interaction.guild.get_role(rol_id)
            kayitsiz_rol = discord.utils.get(interaction.guild.roles, name="Kayıtsız Üye")

            if rol:
                await self.uye.add_roles(rol)
            if kayitsiz_rol:
                await self.uye.remove_roles(kayitsiz_rol)

            oyuncular[str(self.uye.id)] = {
                "isim": self.yeni_isim,
                "mevki": rol_adi,
                "ant_ilerleme": 0,
                "son_ant_zamani": None,
                "penalti_golu": 0,
                "para": 100
            }
            verileri_kaydet(oyuncular)

            embed = discord.Embed(title="✅ Kayıt Tamamlandı!", color=discord.Color.green())
            embed.description = (
                f"🏃‍♂️ {self.uye.mention} Ruthless League lisansı aldı!\n\n"
                f"📋 **İsim:** `{self.yeni_isim}`\n"
                f"🏅 **Rol:** `{rol_adi}`"
            )
            embed.set_thumbnail(url=self.uye.avatar.url if self.uye.avatar else self.uye.default_avatar.url)
            await interaction.response.edit_message(embed=embed, view=self)

        except discord.Forbidden:
            await interaction.response.send_message("❌ Yetki hatası! Botun rolü en üstte olmalı.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Hata: {str(e)}", ephemeral=True)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Üye", style=discord.ButtonStyle.primary, emoji="👤")
    async def uye_buton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rol_ver(interaction, ROL_UYE, "Üye")

    @discord.ui.button(label="Futbolcu", style=discord.ButtonStyle.success, emoji="⚽")
    async def futbolcu_buton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rol_ver(interaction, ROL_FUTBOLCU, "Futbolcu")

    @discord.ui.button(label="Teknik D.", style=discord.ButtonStyle.secondary, emoji="📋")
    async def teknik_buton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rol_ver(interaction, ROL_TEKNIK_D, "Teknik Direktör")


# ==========================================
# TURNUVA KOMUTU 1: .k @Kullanici İsim
# ==========================================
@bot.command(name="k")
@commands.has_permissions(administrator=True)
async def kayit(ctx, uye: discord.Member = None, *, yazi: str = None):
    if uye is None or yazi is None:
        await ctx.send("❌ **Hatalı Kullanım!** Doğru kullanım:\n`.k @kullanıcı [İsim]`\n*(Örnek: `.k @Icardi Mauro Icardi 🇦🇷`)*")
        return

    embed = discord.Embed(title="📋 Kayıt — Rol Seçimi", color=discord.Color.blurple())
    embed.description = (
        f"👤 **Üye:** {uye.mention}\n"
        f"📝 **İsim:** `{yazi}`\n\n"
        f"Aşağıdan bu üyeye verilecek rolü seçin:"
    )
    embed.set_thumbnail(url=uye.avatar.url if uye.avatar else uye.default_avatar.url)

    view = KayitView(uye=uye, yeni_isim=yazi)
    await ctx.send(embed=embed, view=view)

# ==========================================
# TURNUVA KOMUTU 2: .kver @kullanici (Kayıtsız Yapma)
# ==========================================
@bot.command(name="kver")
@commands.has_permissions(administrator=True)
async def kayitsiz(ctx, uye: discord.Member = None):
    if uye is None:
        await ctx.send("❌ **Hatalı Kullanım!** Doğru kullanım: `.kver @kullanıcı`")
        return

    try:
        roller_to_remove = [rol for rol in uye.roles if not rol.is_default()]
        await uye.remove_roles(*roller_to_remove)

        kayitsiz_rol = discord.utils.get(ctx.guild.roles, name="Kayıtsız Üye")
        if kayitsiz_rol:
            await uye.add_roles(kayitsiz_rol)

        await uye.edit(nick=None)

        if str(uye.id) in oyuncular:
            del oyuncular[str(uye.id)]
            verileri_kaydet(oyuncular)

        await ctx.send(f"🗑️ {uye.mention} adlı üyenin tüm rolleri alındı, ismi sıfırlandı ve başarıyla **@Kayıtsız Üye** yapıldı!")

    except discord.Forbidden:
        await ctx.send("❌ **Yetki Hatası!** Botun rolü, elinden alınmak istenen rollerden daha aşağıda kalıyor olabilir. Sunucu ayarlarından botun rolünü yukarı taşıyın.")
    except Exception as e:
        await ctx.send(f"❌ Bir hata oluştu: {str(e)}")

# ==========================================
# MODERATİON: .mute @kullanici [dakika] [sebep]
# ==========================================
@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, uye: discord.Member = None, dakika: int = 10, *, sebep: str = "Sebep belirtilmedi"):
    if uye is None:
        await ctx.send("❌ **Hatalı Kullanım!** Doğru kullanım: `.mute @kullanıcı [dakika] [sebep]`")
        return
    if uye == ctx.author:
        await ctx.send("❌ Kendini mute alamazsın!")
        return
    try:
        sure = timedelta(minutes=dakika)
        await uye.timeout(sure, reason=sebep)
        embed = discord.Embed(title="🔇 Kullanıcı Susturuldu", color=discord.Color.orange())
        embed.add_field(name="👤 Kullanıcı", value=uye.mention, inline=True)
        embed.add_field(name="⏱️ Süre", value=f"{dakika} dakika", inline=True)
        embed.add_field(name="📋 Sebep", value=sebep, inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.set_thumbnail(url=uye.avatar.url if uye.avatar else uye.default_avatar.url)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ **Yetki Hatası!** Botun bu kullanıcıyı mute etme yetkisi yok.")
    except Exception as e:
        await ctx.send(f"❌ Bir hata oluştu: {str(e)}")

# ==========================================
# MODERATİON: .unmute @kullanici
# ==========================================
@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, uye: discord.Member = None):
    if uye is None:
        await ctx.send("❌ **Hatalı Kullanım!** Doğru kullanım: `.unmute @kullanıcı`")
        return
    try:
        await uye.timeout(None)
        embed = discord.Embed(title="🔊 Susturma Kaldırıldı", color=discord.Color.green())
        embed.add_field(name="👤 Kullanıcı", value=uye.mention, inline=True)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.set_thumbnail(url=uye.avatar.url if uye.avatar else uye.default_avatar.url)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ **Yetki Hatası!** Botun bu kullanıcının mute'unu kaldırma yetkisi yok.")
    except Exception as e:
        await ctx.send(f"❌ Bir hata oluştu: {str(e)}")

# ==========================================
# MODERATİON: .kick @kullanici [sebep]
# ==========================================
@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, uye: discord.Member = None, *, sebep: str = "Sebep belirtilmedi"):
    if uye is None:
        await ctx.send("❌ **Hatalı Kullanım!** Doğru kullanım: `.kick @kullanıcı [sebep]`")
        return
    if uye == ctx.author:
        await ctx.send("❌ Kendini kick edemezsin!")
        return
    try:
        embed = discord.Embed(title="👢 Kullanıcı Atıldı", color=discord.Color.red())
        embed.add_field(name="👤 Kullanıcı", value=f"{uye} ({uye.id})", inline=True)
        embed.add_field(name="📋 Sebep", value=sebep, inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.set_thumbnail(url=uye.avatar.url if uye.avatar else uye.default_avatar.url)
        await uye.kick(reason=sebep)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ **Yetki Hatası!** Botun bu kullanıcıyı kick etme yetkisi yok.")
    except Exception as e:
        await ctx.send(f"❌ Bir hata oluştu: {str(e)}")

# ==========================================
# MODERATİON: .ban @kullanici [sebep]
# ==========================================
@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, uye: discord.Member = None, *, sebep: str = "Sebep belirtilmedi"):
    if uye is None:
        await ctx.send("❌ **Hatalı Kullanım!** Doğru kullanım: `.ban @kullanıcı [sebep]`")
        return
    if uye == ctx.author:
        await ctx.send("❌ Kendini ban edemezsin!")
        return
    try:
        embed = discord.Embed(title="🔨 Kullanıcı Banlandı", color=discord.Color.dark_red())
        embed.add_field(name="👤 Kullanıcı", value=f"{uye} ({uye.id})", inline=True)
        embed.add_field(name="📋 Sebep", value=sebep, inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.set_thumbnail(url=uye.avatar.url if uye.avatar else uye.default_avatar.url)
        await uye.ban(reason=sebep, delete_message_days=0)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ **Yetki Hatası!** Botun bu kullanıcıyı ban etme yetkisi yok.")
    except Exception as e:
        await ctx.send(f"❌ Bir hata oluştu: {str(e)}")

# ==========================================
# MODERATİON: .unban [kullanici_id]
# ==========================================
@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, kullanici_id: int = None):
    if kullanici_id is None:
        await ctx.send("❌ **Hatalı Kullanım!** Doğru kullanım: `.unban [kullanıcı_id]`")
        return
    try:
        kullanici = await bot.fetch_user(kullanici_id)
        await ctx.guild.unban(kullanici)
        embed = discord.Embed(title="✅ Ban Kaldırıldı", color=discord.Color.green())
        embed.add_field(name="👤 Kullanıcı", value=f"{kullanici} ({kullanici.id})", inline=True)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.set_thumbnail(url=kullanici.avatar.url if kullanici.avatar else kullanici.default_avatar.url)
        await ctx.send(embed=embed)
    except discord.NotFound:
        await ctx.send("❌ Bu ID'ye sahip banlı bir kullanıcı bulunamadı.")
    except discord.Forbidden:
        await ctx.send("❌ **Yetki Hatası!** Botun ban kaldırma yetkisi yok.")
    except Exception as e:
        await ctx.send(f"❌ Bir hata oluştu: {str(e)}")

# ==========================================
# RP KOMUTU 1: .profil
# ==========================================
@bot.command()
async def profil(ctx, uye: discord.Member = None):
    hedef = uye if uye else ctx.author
    user_id = str(hedef.id)

    if user_id not in oyuncular or (oyuncular[user_id].get("mevki", "YOK") == "YOK" and int(user_id) != OTO_KAYIT_ID and not tac_mu(hedef)):
        await ctx.send(f"❌ {hedef.mention} henüz bir futbolcu lisansına sahip değil! Yetkililer tarafından `.k` komutu ile kaydedilmesi gerekir.")
        return
    # Oto-kayıtlı kullanıcı sisteme kayıtlı değilse anında ekle
    if user_id not in oyuncular:
        oyuncular[user_id] = {
            "isim": OTO_KAYIT_ISIM,
            "mevki": OTO_KAYIT_MEVKI,
            "ant_ilerleme": 0,
            "son_ant_zamani": None,
            "penalti_golu": 0,
            "para": 100
        }
        verileri_kaydet(oyuncular)

    p = oyuncular[user_id]

    embed = discord.Embed(title=f"📋 {p['isim']} • Oyuncu Profili", color=discord.Color.purple())
    embed.set_author(name="🏆 RUTHLESS LEAGUE LICENCE", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_thumbnail(url=hedef.avatar.url if hedef.avatar else hedef.default_avatar.url)

    embed.add_field(name="🏃‍♂️ Mevki", value=f"`{p['mevki']}`", inline=True)
    embed.add_field(name="💰 Piyasa Değeri", value=f"`{p['para']} M€`", inline=True)
    embed.add_field(name="⚽ Penaltı Golleri", value=f"`{p['penalti_golu']} Gol`", inline=True)

    toplam_blok = 10
    dolu_blok = p["ant_ilerleme"]
    bos_blok = toplam_blok - dolu_blok
    ilerleme_cubugu = "<:nokta:1531340691425464380>" * dolu_blok + "<:nokta:1523792841552429126>" * bos_blok
    embed.add_field(name="🏋️‍♂️ Antrenman Seviyesi", value=f"{ilerleme_cubugu} ({p['ant_ilerleme']}/10)", inline=False)

    embed.set_footer(text=f"Ruthless League resmi oyuncu kartı • {hedef.name}")
    await ctx.send(embed=embed)

# ==========================================
# RP KOMUTU 2: .ant (Antrenman)
# ==========================================
@bot.command()
async def ant(ctx):
    user_id = str(ctx.author.id)
    p = oyuncu_kontrol(user_id)

    if p["mevki"] == "YOK" and not tac_mu(ctx.author):
        await ctx.send("❌ Önce bir yetkilinin seni `.k` komutuyla kaydetmesi gerekiyor!")
        return

    simdi = datetime.now()

    if p["son_ant_zamani"]:
        son_ant = datetime.strptime(p["son_ant_zamani"], "%Y-%m-%d %H:%M:%S")
        kalan_sure = son_ant + timedelta(hours=1) - simdi
        if kalan_sure.total_seconds() > 0:
            dakika = int(kalan_sure.total_seconds() // 60)
            await ctx.send(f"❌ **Yorgunsun!** Tekrar antrenman yapmak için `{dakika} dakika` beklemelisin.")
            return

    p["ant_ilerleme"] += 1
    p["para"] += 5
    if p["ant_ilerleme"] > 10:
        p["ant_ilerleme"] = 1

    p["son_ant_zamani"] = simdi.strftime("%Y-%m-%d %H:%M:%S")
    verileri_kaydet(oyuncular)

    toplam_blok = 10
    dolu_blok = p["ant_ilerleme"]
    bos_blok = toplam_blok - dolu_blok
    ilerleme_cubugu = "<:nokta:1531340691425464380>" * dolu_blok + "<:nokta:1523792841552429126>" * bos_blok
    kalan_antrenman = 10 - p["ant_ilerleme"]

    embed = discord.Embed(title=f"🏃‍♂️ {p['isim']} • Antrenman Profili", color=discord.Color.blue())
    embed.add_field(name="🏋️‍♂️ Antrenman Devam Ediyor", value=f"🕒 **Mevcut İlerleme:** {p['ant_ilerleme']} / 10\n{ilerleme_cubugu}", inline=False)
    embed.add_field(name="📋 Antrenman Ayrıntıları", value=f"⏳ **Kalan Gerekli Antrenman:** {kalan_antrenman}\n💰 **Piyasa Değeri Artışı:** +5 M€\n🕒 **Sonraki Antrenman:** Bir saat sonra, kaçırma!", inline=False)
    embed.set_footer(text="ℹ️ Ruthless League serisini bozmadan devam ederek istatistiklerinizi yükseltin.")
    embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

    await ctx.send(embed=embed)

# ==========================================
# RP KOMUTU 3: .penaltı
# ==========================================
@bot.command(name="penaltı", aliases=["penalti"])
async def penalti(ctx):
    user_id = str(ctx.author.id)
    p = oyuncu_kontrol(user_id)

    if p["mevki"] == "YOK" and not tac_mu(ctx.author):
        await ctx.send("❌ Önce bir yetkilinin seni `.k` komutuyla kaydetmesi gerekiyor!")
        return

    simdi = datetime.now()
    son_penalti = p.get("son_penalti_zamani")
    if son_penalti:
        try:
            son_kullanim = datetime.strptime(son_penalti, "%Y-%m-%d %H:%M:%S")
            kalan_sure = son_kullanim + timedelta(hours=1) - simdi
            if kalan_sure.total_seconds() > 0:
                dakika = max(1, int((kalan_sure.total_seconds() + 59) // 60))
                cooldown_embed = discord.Embed(
                    color=discord.Color.from_rgb(0, 0, 0),
                    description=(
                        f"<a:saat:1545088358353731705> Penaltı hakkın henüz yenilenmedi.\n\n"
                        f"Yeni hakkını **{dakika} dakika** sonra kullanabilirsin."
                    ),
                )
                await ctx.send(embed=cooldown_embed)
                return
        except ValueError:
            p.pop("son_penalti_zamani", None)

    senaryolar = [
        {
            "mesaj": (
                "<:penalti:1545845312306942002> PENALTI GOOOOLLLL"
                "<a:peepoclap:1544858466752008263>\n\n"
                "<a:BTFS_ZirveElmas:1544843346479161424> Değer Kazancı 2M\n\n"
                "<a:saat:1545088358353731705> Sonraki Hakkın 1 Saat Sonra."
            ),
            "gol": True,
        },
        {
            "mesaj": (
                "<:penaltikacti:1544828350969942107> VURUŞŞ AUT "
                "<:emoji_130:1545847240357060731>\n\n"
                "<:popeyes62:1544843272705540246> Değer Kazancı 0\n\n"
                "<a:saat:1545088358353731705> Üzülme 1 Saat Sonra Yeniden Kullanabilirsin."
            ),
            "gol": False,
        },
        {
            "mesaj": (
                "<:penalti:1545845309945421854> VEEE DİREEKK "
                "<:baggio:1545846769353629706>\n\n"
                "<:popeyes62:1544843272705540246> Değer Kazancı 0\n\n"
                "<a:saat:1545088358353731705> Ayakta Kalmanın Manası Yok 1 Saat Sonra Yeniden Burada Olacaksın."
            ),
            "gol": False,
        },
        {
            "mesaj": (
                "<:penaltikacti:1544828350969942107> GÜÇSÜZ BİR VURUŞ VE KALECİ "
                "<:kurtaris:1545849244173344798>\n\n"
                "<:popeyes62:1544843272705540246> Değer Kazancı 0\n\n"
                "<a:saat:1545088358353731705> 1 Saat İçinde O Şişeyi İmha Edip Geri Gel."
            ),
            "gol": False,
        },
    ]
    sonuc = random.choice(senaryolar)

    if sonuc["gol"]:
        p["penalti_golu"] = p.get("penalti_golu", 0) + 1
        p["para"] = p.get("para", 0) + 2

    p["son_penalti_zamani"] = simdi.strftime("%Y-%m-%d %H:%M:%S")
    verileri_kaydet(oyuncular)
    embed = discord.Embed(
        color=discord.Color.from_rgb(0, 0, 0),
        description=sonuc["mesaj"],
    )
    await ctx.send(embed=embed)

# ==========================================
# OTO ROL KURULUM KOMUTU: .sjbj
# ==========================================
@bot.command(name="sjbj")
@commands.has_permissions(administrator=True)
async def otorol_kur(ctx):
    metin = (
        "**RUTHLESS LEAUGE OTO ROL**\n\n"
        "**『 <:top:1527786179506733136>  』 Maçlardan haberdar olmak için emojiye basın.\n"
        "『 <:kutu:1527785963886088263>  』 Çekilişlerden haberdar olmak için emojiye basın.\n"
        "『<:gazete:1527785752971182171>  』Haberlerden haberdar olmak için emojiye basın.\n"
        "『🏆 』 Lig duyurularından haberdar olmak için emojiye basın.\n"
        "『<:takvim:1527785588906791093> 』Maçların fikstürlerinden haberdar olmak için emojiye basın.\n"
        "**"
    )

    mesaj = await ctx.send(metin)

    ozel_emojiler = [
        (1527786179506733136, "top"),
        (1527785963886088263, "kutu"),
        (1527785752971182171, "gazete"),
        (1527785588906791093, "takvim"),
    ]

    for emoji_id, emoji_adi in ozel_emojiler:
        emoji = discord.utils.get(ctx.guild.emojis, id=emoji_id)
        if emoji:
            await mesaj.add_reaction(emoji)

    await mesaj.add_reaction("🏆")

    otorol_veri["mesaj_id"] = str(mesaj.id)
    otorol_kaydet(otorol_veri)

    await ctx.message.delete()


# ==========================================
# KAP TRANSFer SİSTEMİ
# ==========================================

TAKIMLAR = [
    {"ad": "Dortmund",  "emoji": "<:dortmund:1527776798513958983>",  "rol_id": 1522570889516945419},
    {"ad": "Barcelona", "emoji": "<:barcelona:1527776939182395634>", "rol_id": 1522570886207766559},
    {"ad": "PSG",       "emoji": "<:PSG:1527777062562041930>",       "rol_id": 1522570890661859398},
    {"ad": "Bayern",    "emoji": "<:Bayern:1527777181755772949>",    "rol_id": 1522570887990083584},
    {"ad": "Arsenal",   "emoji": "<:arsenal:1527777372340752517>",   "rol_id": 1522570898308337714},
    {"ad": "Real",      "emoji": "<:real:1527777951289053277>",      "rol_id": 1522570885490278420},
    {"ad": "Marsilya",  "emoji": "<:marsilya:1527778265341755442>",  "rol_id": 1522570891777806437},
    {"ad": "United",    "emoji": "<:united:1527778391884042353>",    "rol_id": 1522570894013366434},
    {"ad": "City",      "emoji": "<:city:1527778582603104266>",      "rol_id": 1522570892612342001},
    {"ad": "Juventus",  "emoji": "<:juventus:1527778702727839926>",  "rol_id": 1522570896206856202},
    {"ad": "Chelsea",   "emoji": "<:chelsea:1527778840074518588>",   "rol_id": 1522570897318346964},
    {"ad": "Napoli",    "emoji": "<:napoli:1527778984614564052>",    "rol_id": 1522570894919204897},
]

TAKIM_ROL_HARITA = {t["rol_id"]: t for t in TAKIMLAR}
TUM_TAKIM_ROLLERI  = [t["rol_id"] for t in TAKIMLAR]
kap_verileri = {}  # hedef_user_id → form verisi

def takim_bilgi(rol_id: int):
    if rol_id == 0:
        return {"ad": "Klüpsüz", "emoji": "🚫"}
    return TAKIM_ROL_HARITA.get(rol_id, {"ad": "Bilinmiyor", "emoji": "❓"})


class KapTuruSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="📦 Kiralık Sözleşme", value="Kiralık Sözleşme"),
            discord.SelectOption(label="💰 Satın Alım",       value="Satın Alım"),
        ]
        super().__init__(placeholder="📋 KAP Türü Seçin...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.kap_turu = self.values[0]
        await interaction.response.defer()


class EskiKulupSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label="- Klüpsüz", value="0")] + \
                  [discord.SelectOption(label=f"- {t['ad']}", value=str(t["rol_id"])) for t in TAKIMLAR]
        super().__init__(placeholder="📤 Eski / Çıkış Yapan Kulüp...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.eski_kulup_rol = int(self.values[0])
        await interaction.response.defer()


class YeniKulupSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=t["ad"], value=str(t["rol_id"])) for t in TAKIMLAR]
        super().__init__(placeholder="📥 Yeni / Anlaşma Sağlanan Kulüp...", options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        self.view.yeni_kulup_rol = int(self.values[0])
        await interaction.response.defer()


class KapFormView(discord.ui.View):
    def __init__(self, yetkili_id: int, hedef_id: int):
        super().__init__(timeout=300)
        self.yetkili_id     = yetkili_id
        self.hedef_id       = hedef_id
        self.kap_turu       = None
        self.eski_kulup_rol = None
        self.yeni_kulup_rol = None
        self.add_item(KapTuruSelect())
        self.add_item(EskiKulupSelect())
        self.add_item(YeniKulupSelect())

    @discord.ui.button(label="Devam Et →", style=discord.ButtonStyle.success, row=3)
    async def devam(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.yetkili_id:
            await interaction.response.send_message("❌ Bu formu sadece komutu kullanan yetkili doldurabilir!", ephemeral=True)
            return
        if not self.kap_turu or not self.eski_kulup_rol or not self.yeni_kulup_rol:
            await interaction.response.send_message("❌ Lütfen tüm seçenekleri doldurun!", ephemeral=True)
            return
        await interaction.response.send_modal(
            KapModal(self.yetkili_id, self.hedef_id, self.kap_turu, self.eski_kulup_rol, self.yeni_kulup_rol)
        )


class KapModal(discord.ui.Modal, title="📋 KAP Sözleşme Detayları"):
    sozlesme_suresi = discord.ui.TextInput(label="📅 Sözleşme Süresi",    placeholder="Örn: 1.5 Sezon", max_length=100)
    sezonluk_maas   = discord.ui.TextInput(label="💵 Sezonluk Maaş",      placeholder="Örn: 5M€",       max_length=150)
    bonservis       = discord.ui.TextInput(label="🛒 Bonservis Bedeli",    placeholder="Örn: 78M€",      max_length=150)
    ek_maddeler     = discord.ui.TextInput(
        label="📌 Sözleşme Ek Maddeleri & Şartlar",
        placeholder="Opsiyonel...",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    def __init__(self, yetkili_id, hedef_id, kap_turu, eski_kulup_rol, yeni_kulup_rol):
        super().__init__()
        self.yetkili_id     = yetkili_id
        self.hedef_id       = hedef_id
        self.kap_turu       = kap_turu
        self.eski_kulup_rol = eski_kulup_rol
        self.yeni_kulup_rol = yeni_kulup_rol

    async def on_submit(self, interaction: discord.Interaction):
        eski = takim_bilgi(self.eski_kulup_rol)
        yeni = takim_bilgi(self.yeni_kulup_rol)

        kap_verileri[self.hedef_id] = {
            "yetkili_id":      self.yetkili_id,
            "yetkili_ad":      interaction.user.display_name,
            "kap_turu":        self.kap_turu,
            "eski_kulup_rol":  self.eski_kulup_rol,
            "yeni_kulup_rol":  self.yeni_kulup_rol,
            "sozlesme_suresi": self.sozlesme_suresi.value,
            "sezonluk_maas":   self.sezonluk_maas.value,
            "bonservis":       self.bonservis.value,
            "ek_maddeler":     self.ek_maddeler.value or "—",
        }

        hedef = interaction.guild.get_member(self.hedef_id)
        hedef_mention = hedef.mention if hedef else f"<@{self.hedef_id}>"

        embed = discord.Embed(title="📄 KAP FORM: RESMİ BİR BİLDİRİM BİLGİLERİ", color=discord.Color.gold())
        embed.add_field(name="🧢 Futbolcu",                        value=f"└ {hedef_mention}",             inline=False)
        embed.add_field(name="📦 KAP Türü",                        value=f"└ {self.kap_turu}",             inline=False)
        embed.add_field(name="📤 Eski / Çıkış Yapan Kulüp",        value=f"└ {eski['emoji']} {eski['ad']}", inline=False)
        embed.add_field(name="📥 Yeni / Anlaşma Sağlanan Kulüp",   value=f"└ {yeni['emoji']} {yeni['ad']}", inline=False)
        embed.add_field(name="📅 Sözleşme Süresi",                 value=f"└ {self.sozlesme_suresi.value}", inline=False)
        embed.add_field(name="💵 Sezonluk Maaş",                   value=f"└ {self.sezonluk_maas.value}",  inline=False)
        embed.add_field(name="🛒 Ödenen / Anlaşılan Bonservis",    value=f"└ {self.bonservis.value}",      inline=False)
        embed.add_field(name="📌 Sözleşme Ek Maddeleri & Şartlar", value=f"└ {self.ek_maddeler.value or '—'}", inline=False)
        embed.set_footer(text=f"Formu Düzenleyen Yetkili: {interaction.user.display_name} • Ruthless League")

        await interaction.response.send_message(
            content=f"📋 {hedef_mention} sözleşmeni inceleyip imzalayabilirsin:",
            embed=embed,
            view=KapImzalaView(self.hedef_id)
        )


class KapImzalaView(discord.ui.View):
    def __init__(self, hedef_id: int):
        super().__init__(timeout=600)
        self.hedef_id = hedef_id

    @discord.ui.button(label="✍️ Sözleşmeyi İmzala", style=discord.ButtonStyle.danger)
    async def imzala(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.hedef_id:
            await interaction.response.send_message("❌ Bu sözleşmeyi sadece ilgili futbolcu imzalayabilir!", ephemeral=True)
            return

        veri = kap_verileri.get(self.hedef_id)
        if not veri:
            await interaction.response.send_message("❌ Form verisi bulunamadı. Tekrar deneyin.", ephemeral=True)
            return

        uye = interaction.guild.get_member(self.hedef_id)
        if not uye:
            await interaction.response.send_message("❌ Üye sunucuda bulunamadı.", ephemeral=True)
            return

        kaldir = [interaction.guild.get_role(r) for r in TUM_TAKIM_ROLLERI
                  if interaction.guild.get_role(r) in uye.roles]
        if kaldir:
            await uye.remove_roles(*kaldir)

        yeni_rol = interaction.guild.get_role(veri["yeni_kulup_rol"])
        if yeni_rol:
            await uye.add_roles(yeni_rol)

        eski = takim_bilgi(veri["eski_kulup_rol"])
        yeni = takim_bilgi(veri["yeni_kulup_rol"])
        yetkili = interaction.guild.get_member(veri["yetkili_id"])
        yetkili_mention = yetkili.mention if yetkili else f"<@{veri['yetkili_id']}>"

        embed = discord.Embed(
            title="🚀 KAP BİLDİRİMİ RESMİYET KAZANDI",
            description=(
                f"{uye.mention} isimli futbolcunun sözleşme protokolü\n"
                f"kulüplerin ve oyuncunun karşılıklı mutabakatıyla tescil edilmiş\n"
                f"ve transfer başarıyla gerçekleştirilmiştir.\n"
                f"**PROTOKOL ONAYLANDI!**\n\n"
                f"🖊️ **İşlemi Gerçekleştiren Yetkili:** {yetkili_mention}"
            ),
            color=discord.Color.green()
        )
        embed.add_field(name="📄 KAP FORM: RESMİ BİR BİLDİRİM BİLGİLERİ", value="\u200b",                  inline=False)
        embed.add_field(name="🧢 Futbolcu",                          value=f"└ {uye.mention}",               inline=False)
        embed.add_field(name="📦 KAP Türü",                          value=f"└ {veri['kap_turu']}",          inline=False)
        embed.add_field(name="📤 Eski / Çıkış Yapan Kulüp",          value=f"└ {eski['emoji']} {eski['ad']}", inline=False)
        embed.add_field(name="📥 Yeni / Anlaşma Sağlanan Kulüp",     value=f"└ {yeni['emoji']} {yeni['ad']}", inline=False)
        embed.add_field(name="📅 Sözleşme Süresi",                   value=f"└ {veri['sozlesme_suresi']}",   inline=False)
        embed.add_field(name="💵 Sezonluk Maaş",                     value=f"└ {veri['sezonluk_maas']}",     inline=False)
        embed.add_field(name="🛒 Ödenen / Anlaşılan Bonservis",      value=f"└ {veri['bonservis']}",         inline=False)
        embed.add_field(name="📌 Sözleşme Ek Maddeleri & Şartlar",   value=f"└ {veri['ek_maddeler']}",      inline=False)
        embed.set_footer(text=f"Formu Düzenleyen Yetkili: {veri['yetkili_ad']} • Ruthless League")

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(embed=embed)
        kap_verileri.pop(self.hedef_id, None)


class KapBaslatView(discord.ui.View):
    def __init__(self, yetkili_id: int, hedef_id: int):
        super().__init__(timeout=600)
        self.yetkili_id = yetkili_id
        self.hedef_id   = hedef_id

    @discord.ui.button(label="📋 KAP Formunu Doldur", style=discord.ButtonStyle.primary)
    async def form_ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.yetkili_id:
            await interaction.response.send_message("❌ Bu formu sadece komutu kullanan yetkili doldurabilir!", ephemeral=True)
            return
        embed = discord.Embed(
            title="📋 KAP Transfer Formu",
            description="Sırasıyla **KAP türünü**, **eski kulübü** ve **yeni kulübü** seç.\nSonra **Devam Et** butonuna bas.",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, view=KapFormView(self.yetkili_id, self.hedef_id), ephemeral=True)


@bot.command(name="kap")
async def kap(ctx, uye: discord.Member = None):
    teknik_d = discord.utils.get(ctx.guild.roles, name="Teknik Direktör")
    if (not teknik_d or teknik_d not in ctx.author.roles) and not tac_mu(ctx.author):
        await ctx.send("❌ Bu komutu sadece **Teknik Direktör** veya **tac** rolüne sahip kişiler kullanabilir.", delete_after=5)
        await ctx.message.delete()
        return
    if uye is None:
        await ctx.send("❌ Kullanım: `.kap @kullanıcı`", delete_after=5)
        await ctx.message.delete()
        return

    embed = discord.Embed(
        title="🚀 KAP Transfer Bildirimi",
        description=(
            f"**Futbolcu:** {uye.mention}\n"
            f"**İşlemi Başlatan:** {ctx.author.mention}\n\n"
            f"📋 {ctx.author.mention} formu dolduracak, ardından {uye.mention} sözleşmeyi imzalayacak."
        ),
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=uye.avatar.url if uye.avatar else uye.default_avatar.url)
    embed.set_footer(text="⚽ Ruthless League • KAP Transfer Sistemi")
    await ctx.send(embed=embed, view=KapBaslatView(ctx.author.id, uye.id))
    await ctx.message.delete()


# ==========================================
# TAKIM BİLGİSİ KOMUTU
# ==========================================
@bot.command(name="takim", aliases=["takım"])
async def takim_info(ctx, *, takim_adi: str = None):
    if not takim_adi:
        await ctx.send("❌ Kullanım: `.takim <takım adı>` — Örn: `.takim dortmund`", delete_after=5)
        return

    aranan = takim_adi.strip().lower()
    eslesen = None
    for t in TAKIMLAR:
        if aranan in t["ad"].lower():
            eslesen = t
            break

    if not eslesen:
        isimler = ", ".join(t["ad"] for t in TAKIMLAR)
        await ctx.send(f"❌ `{takim_adi}` adında bir takım bulunamadı.\n📋 Mevcut takımlar: {isimler}", delete_after=10)
        return

    rol = ctx.guild.get_role(eslesen["rol_id"])
    if not rol:
        await ctx.send("❌ Takım rolü sunucuda bulunamadı.", delete_after=5)
        return

    td_rolu      = discord.utils.get(ctx.guild.roles, name="Teknik Direktör")
    kaptan_rolu  = discord.utils.get(ctx.guild.roles, name="Takım Kaptanı")
    oyuncular_listesi = [m for m in rol.members if not m.bot]

    td_uye     = None
    kaptan_uye = None
    for m in oyuncular_listesi:
        if td_rolu and td_rolu in m.roles and td_uye is None:
            td_uye = m
        if kaptan_rolu and kaptan_rolu in m.roles and kaptan_uye is None:
            kaptan_uye = m

    toplam_butce = 0
    toplam_deger = 0
    oyuncu_satirlari = []

    for m in oyuncular_listesi:
        uid = str(m.id)
        veri = oyuncular.get(uid, {})
        isim   = veri.get("isim", m.display_name)
        mevki  = veri.get("mevki", "—")
        para   = veri.get("para", 0)
        # Kulüp bütçesi = Teknik Direktörün parası
        if td_uye and m.id == td_uye.id:
            toplam_butce = para

        nick = m.nick or m.display_name
        deger_esleme = re.search(r"(\d+(?:[.,]\d+)?)\s*M€", nick, re.IGNORECASE)
        oyuncu_degeri = 0
        deger_str = "—"
        if deger_esleme:
            try:
                oyuncu_degeri = float(deger_esleme.group(1).replace(",", "."))
                toplam_deger += oyuncu_degeri
                deger_str = f"{deger_esleme.group(1)}M€"
            except ValueError:
                pass

        if td_uye and m.id == td_uye.id:
            oyuncu_satirlari.append(f"🎖️ **{isim}** • {mevki} • {deger_str} *(TD)*")
        else:
            oyuncu_satirlari.append(f"⚽ **{isim}** • {mevki} • {deger_str}")

    oyuncu_sayisi = len(oyuncular_listesi)
    oyuncu_metni = "\n".join(oyuncu_satirlari) if oyuncu_satirlari else "*Kadro boş*"

    embed = discord.Embed(
        title=f"{eslesen['emoji']} {eslesen['ad']} — Takım Bilgisi",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="👤 Teknik Direktör",
        value=td_uye.mention if td_uye else "*Atanmamış*",
        inline=True
    )
    embed.add_field(
        name="👥 Oyuncu Sayısı",
        value=f"`{oyuncu_sayisi}` oyuncu",
        inline=True
    )
    embed.add_field(
        name="💰 Toplam Bütçe",
        value=f"`{toplam_butce} M€`",
        inline=True
    )
    embed.add_field(
        name="📈 Takım Değeri",
        value=f"`{toplam_deger:g} M€`" if toplam_deger else "`—`",
        inline=True
    )
    embed.add_field(
        name="📋 Kadro",
        value=oyuncu_metni if len(oyuncu_metni) <= 1024 else oyuncu_metni[:1020] + "...",
        inline=False
    )
    embed.set_footer(text="⚽ Ruthless League • Takım Bilgisi")

    await ctx.send(embed=embed)


# ==========================================
# PARA KOMUTLARI
# ==========================================

@bot.command(name="dver")
async def deger_ver(ctx, hedef: discord.Member = None, miktar: int = None, *, sebep: str = "Sebep belirtilmedi"):
    """.dver @kullanici <miktar> [sebep] — Nick'teki M€ değerine miktar ekler. Sadece Kayıt Yetkilisi rolü."""
    kayit_rol = discord.utils.get(ctx.guild.roles, name="Kayıt Yetkilisi")
    if not kayit_rol or kayit_rol not in ctx.author.roles:
        await ctx.send("❌ Bu komutu sadece **Kayıt Yetkilisi** rolüne sahip kişiler kullanabilir.", delete_after=5)
        await ctx.message.delete()
        return

    if hedef is None or miktar is None:
        await ctx.send("❌ **Hatalı Kullanım!** Doğru kullanım: `.dver @kullanıcı <miktar> [sebep]`\nÖrnek: `.dver @Messi 3 Antrenman ödülü`")
        return
    if miktar <= 0:
        await ctx.send("❌ Miktar 0'dan büyük olmalı!")
        return

    futbolcu_rol = discord.utils.get(ctx.guild.roles, name="Futbolcu")
    if not futbolcu_rol or futbolcu_rol not in hedef.roles:
        await ctx.send(f"❌ {hedef.mention} **Futbolcu** rolüne sahip değil! Bu komut yalnızca futbolcularda çalışır.")
        return

    mevcut_nick = hedef.nick or hedef.display_name
    esleme = re.search(r'(\d+(?:[.,]\d+)?)\s*M€\s*$', mevcut_nick, re.IGNORECASE)
    if not esleme:
        await ctx.send(
            f"❌ {hedef.mention} nickinde `M€` formatında bir değer bulunamadı!\n"
            f"Beklenen format: `Messi | 🇦🇷 | SLK | 1M€`"
        )
        return

    mevcut_str  = esleme.group(1).replace(",", ".")
    mevcut_deger = float(mevcut_str)
    yeni_deger   = mevcut_deger + miktar

    # Tam sayıysa ondalık gösterme
    yeni_str = str(int(yeni_deger)) if yeni_deger == int(yeni_deger) else str(yeni_deger)

    yeni_nick = re.sub(r'\d+(?:[.,]\d+)?\s*M€\s*$', f'{yeni_str}M€', mevcut_nick, flags=re.IGNORECASE)

    try:
        await hedef.edit(nick=yeni_nick)
    except discord.Forbidden:
        await ctx.send("❌ Yetki hatası! Botun rolü bu üyenin rolünden yukarıda olmalı.")
        return

    # para alanını da güncelle
    uid = str(hedef.id)
    if uid in oyuncular:
        oyuncular[uid]["para"] = int(yeni_deger) if yeni_deger == int(yeni_deger) else yeni_deger
        verileri_kaydet(oyuncular)

    embed = discord.Embed(title="📈 Piyasa Değeri Güncellendi", color=discord.Color.green())
    embed.set_thumbnail(url=hedef.avatar.url if hedef.avatar else hedef.default_avatar.url)
    embed.add_field(name="👤 Futbolcu",    value=hedef.mention,              inline=True)
    embed.add_field(name="💰 Eski Değer",  value=f"`{mevcut_str}M€`",        inline=True)
    embed.add_field(name="➕ Eklenen",     value=f"`+{miktar}M€`",           inline=True)
    embed.add_field(name="💎 Yeni Değer",  value=f"**{yeni_str}M€**",        inline=True)
    embed.add_field(name="📝 Yeni Nick",   value=f"`{yeni_nick}`",           inline=True)
    embed.add_field(name="📋 Sebep",       value=sebep,                      inline=False)
    embed.set_footer(text=f"İşlemi yapan: {ctx.author.display_name} • Ruthless League")
    await ctx.send(embed=embed)


@bot.command(name="para")
async def para_goster(ctx):
    """Kendi para miktarını gösterir."""
    user_id = str(ctx.author.id)
    if (user_id not in oyuncular or oyuncular[user_id].get("mevki", "YOK") == "YOK") and not tac_mu(ctx.author):
        await ctx.send("❌ Henüz kayıtlı değilsin! Bir yetkiliden `.k` komutuyla kaydedilmeni iste.")
        return
    if user_id not in oyuncular:
        oyuncular[user_id] = {"isim": ctx.author.display_name, "mevki": "tac", "ant_ilerleme": 0, "son_ant_zamani": None, "penalti_golu": 0, "para": 0}
        verileri_kaydet(oyuncular)
    p = oyuncular[user_id]
    embed = discord.Embed(
        title="💰 Hesap Bakiyesi",
        color=discord.Color.gold()
    )
    embed.set_author(name=p["isim"], icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    embed.add_field(name="💵 Mevcut Para", value=f"**{p['para']} M€**", inline=False)
    embed.set_footer(text="⚽ Ruthless League • Para Sistemi")
    await ctx.send(embed=embed)


@bot.command(name="parag")
async def para_gonder(ctx, miktar: int = None, hedef: discord.Member = None):
    """Para transferi: .parag <miktar> @kullanici"""
    if miktar is None or hedef is None:
        await ctx.send("❌ **Hatalı Kullanım!** Doğru kullanım: `.parag <miktar> @kullanıcı`\nÖrnek: `.parag 50 @Icardi`")
        return
    if miktar <= 0:
        await ctx.send("❌ Gönderilecek miktar 0'dan büyük olmalı!")
        return
    if hedef.id == ctx.author.id:
        await ctx.send("❌ Kendine para gönderemezsin!")
        return

    gonderen_id = str(ctx.author.id)
    alici_id    = str(hedef.id)

    if (gonderen_id not in oyuncular or (oyuncular[gonderen_id].get("mevki", "YOK") == "YOK" and ctx.author.id != OTO_KAYIT_ID)) and not tac_mu(ctx.author):
        await ctx.send("❌ Önce kayıtlı olman gerekiyor!")
        return
    if gonderen_id not in oyuncular:
        oyuncular[gonderen_id] = {"isim": ctx.author.display_name, "mevki": "tac", "ant_ilerleme": 0, "son_ant_zamani": None, "penalti_golu": 0, "para": 0}
        verileri_kaydet(oyuncular)
    if (alici_id not in oyuncular or (oyuncular[alici_id].get("mevki", "YOK") == "YOK" and hedef.id != OTO_KAYIT_ID)) and not tac_mu(hedef):
        await ctx.send(f"❌ {hedef.mention} kayıtlı bir oyuncu değil!")
        return
    if alici_id not in oyuncular:
        oyuncular[alici_id] = {"isim": hedef.display_name, "mevki": "tac", "ant_ilerleme": 0, "son_ant_zamani": None, "penalti_golu": 0, "para": 0}
        verileri_kaydet(oyuncular)

    gonderen = oyuncular[gonderen_id]
    alici    = oyuncular[alici_id]

    if gonderen["para"] < miktar:
        await ctx.send(f"❌ Yetersiz bakiye! Elinde sadece **{gonderen['para']} M€** var.")
        return

    gonderen["para"] -= miktar
    alici["para"]    += miktar
    verileri_kaydet(oyuncular)

    embed = discord.Embed(title="💸 Para Transferi Gerçekleşti", color=discord.Color.green())
    embed.add_field(name="📤 Gönderen", value=f"{ctx.author.mention}\n*Yeni bakiye: {gonderen['para']}*", inline=True)
    embed.add_field(name="💰 Miktar",   value=f"**{miktar}**",                                            inline=True)
    embed.add_field(name="📥 Alan",     value=f"{hedef.mention}\n*Yeni bakiye: {alici['para']}*",         inline=True)
    embed.set_footer(text="⚽ Ruthless League • Para Sistemi")
    await ctx.send(embed=embed)


@bot.command(name="paraekle")
async def para_ekle(ctx, hedef: discord.Member = None, miktar: int = None):
    """TAC rolü: kimseden almadan para ekler. .paraekle @kullanici <miktar>"""
    tac_rol = discord.utils.get(ctx.guild.roles, name="tac")
    if not tac_rol or tac_rol not in ctx.author.roles:
        await ctx.send("❌ Bu komutu sadece **TAC** rolüne sahip kişiler kullanabilir.", delete_after=5)
        await ctx.message.delete()
        return
    if miktar is None or hedef is None:
        await ctx.send("❌ **Hatalı Kullanım!** Doğru kullanım: `.paraekle <miktar> @kullanıcı`\nÖrnek: `.paraekle 100 @Icardi`")
        return
    if miktar <= 0:
        await ctx.send("❌ Eklenecek miktar 0'dan büyük olmalı!")
        return

    alici_id = str(hedef.id)
    if (alici_id not in oyuncular or (oyuncular[alici_id].get("mevki", "YOK") == "YOK" and hedef.id != OTO_KAYIT_ID)) and not tac_mu(hedef):
        await ctx.send(f"❌ {hedef.mention} kayıtlı bir oyuncu değil!")
        return
    if alici_id not in oyuncular:
        oyuncular[alici_id] = {"isim": hedef.display_name, "mevki": "tac", "ant_ilerleme": 0, "son_ant_zamani": None, "penalti_golu": 0, "para": 0}
        verileri_kaydet(oyuncular)

    oyuncular[alici_id]["para"] += miktar
    verileri_kaydet(oyuncular)

    embed = discord.Embed(title="💰 Para Eklendi", color=discord.Color.blurple())
    embed.add_field(name="👤 Oyuncu",      value=hedef.mention,                           inline=True)
    embed.add_field(name="➕ Eklenen",     value=f"**{miktar}**",                          inline=True)
    embed.add_field(name="💵 Yeni Bakiye", value=f"**{oyuncular[alici_id]['para']}**",     inline=True)
    embed.set_footer(text=f"İşlemi yapan: {ctx.author.display_name} • Ruthless League")
    await ctx.send(embed=embed)


# ==========================================
# BAŞLATMA
# ==========================================
keep_alive()
start_ping()
bot.run(os.environ['DISCORD_TOKEN'])
