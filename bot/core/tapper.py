import asyncio
import random
import sys
import traceback
from time import time
from urllib.parse import unquote

import hmac
import hashlib
import aiohttp
from datetime import datetime

import pytz
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw import functions
from pyrogram.raw.functions.messages import RequestWebView
from bot.core.agents import generate_random_user_agent
from bot.config import settings
import cloudscraper

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from random import randint

class Tapper:
    def __init__(self, tg_client: Client):
        self.tg_client = tg_client
        self.session_name = tg_client.name
        self.first_name = ''
        self.last_name = ''
        self.user_id = ''
        self.auth_token = ""
        self.last_claim = None
        self.last_checkin = None
        self.balace = 0
        self.maxtime = 0
        self.fromstart = 0
        self.checked = [False]*5
        self.ref_id = None
        self.access_token = None
        self.logged = False

    async def get_tg_web_data(self, proxy: str | None) -> str:
        try:
            if settings.REF_LINK == "":
                ref_param = "referredBy=6624523270"
            else:
                ref_param =settings.REF_LINK.split("=")[1] + "=" + settings.REF_LINK.split("=")[2]
        except:
            logger.error(f"{self.session_name} | Ref link invaild please check again !")
            sys.exit()
        # print(ref_param)
        self.ref_id = settings.REF_LINK.split('=')[2] if settings.REF_LINK != "" else "6624523270"
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()
                    start_command_found = False
                    async for message in self.tg_client.get_chat_history('BybitCoinsweeper_Bot'):
                        if (message.text and message.text.startswith('/start')) or (
                                message.caption and message.caption.startswith('/start')):
                            start_command_found = True
                            break
                    if not start_command_found:
                        peer = await self.tg_client.resolve_peer('BybitCoinsweeper_Bot')
                        await self.tg_client.invoke(
                            functions.messages.StartBot(
                                bot=peer,
                                peer=peer,
                                start_param=ref_param,
                                random_id=randint(1, 9999999),
                            )
                        )
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            while True:
                try:
                    peer = await self.tg_client.resolve_peer('BybitCoinsweeper_Bot')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"<light-yellow>{self.session_name}</light-yellow> | FloodWait {fl}")
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Sleep {fls}s")

                    await asyncio.sleep(fls + 3)

            web_view = await self.tg_client.invoke(RequestWebView(
                peer=peer,
                bot=peer,
                platform='android',
                from_bot_menu=False,
                url="https://bybitcoinsweeper.com",
                start_param=ref_param
            ))

            auth_url = web_view.url
            # print(auth_url)
            tg_web_data = unquote(
                string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))

            self.user_id = tg_web_data.split('"id":')[1].split(',"first_name"')[0]
            self.first_name = tg_web_data.split('"first_name":"')[1].split('","last_name"')[0]
            self.last_name = tg_web_data.split('"last_name":"')[1].split('","username"')[0]

            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0])

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Unknown error during Authorization: "
                         f"{error}")
            await asyncio.sleep(delay=3)


    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy):
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
            return True
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")
            return False


    def login(self, session: cloudscraper.CloudScraper):
        try:
            payload = {
                "initData": self.auth_token,
                "referredBy": str(self.ref_id)
            }
            # print(payload)
            res = session.post("https://api.bybitcoinsweeper.com/api/auth/login", headers=headers, json=payload)
            res.raise_for_status()
            user_data = res.json()
            # print(user_data)
            logger.success(f"{self.session_name} | Logged in Successfully!")
            headers['Authorization'] = f"Bearer {user_data['accessToken']}"
            self.access_token = {user_data['accessToken']}
            self.logged = True
        except Exception as e:
            traceback.print_exc()
            logger.error(f"{self.session_name} | Unknown error while trying to login: {e}")


    def get_me(self, session: cloudscraper.CloudScraper):
        res = session.get("https://api.bybitcoinsweeper.com/api/users/me", headers=headers)
        if res.status_code == 200:
            user = res.json()
            self.user_id = user['id']
            logger.info(f"{self.session_name} | Balance: <light-yellow>{user['score']}</light-yellow>")

        else:
            logger.warning(f"{self.session_name} | <yellow>Get user info failed: {res.status_code} | {res.json()}</yellow>")

    def refresh_token(self, session: cloudscraper.CloudScraper):
        payload = {
            "refreshToken": self.access_token
        }
        res = session.post("https://api.bybitcoinsweeper.com/api/auth/refresh-token", headers=headers, json=payload)
        if res.status_code == 201:
            self.access_token = res.json()['accessToken']
        else:
            logger.warning(f"{self.session_name} | <yellow>Refresh token failed: {res.text}</yellow>")
    async def run(self, proxy: str | None) -> None:
        access_token_created_time = 0
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        headers["User-Agent"] = generate_random_user_agent(device_type='android', browser_type='chrome')
        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)
        session = cloudscraper.create_scraper()

        if proxy:
            proxy_check = await self.check_proxy(http_client=http_client, proxy=proxy)
            if proxy_check:
                proxy_type = proxy.split(':')[0]
                proxies = {
                    proxy_type: proxy
                }
                session.proxies.update(proxies)
                logger.info(f"{self.session_name} | bind with proxy ip: {proxy}")

        token_live_time = randint(3500, 3600)
        while True:
            try:
                if time() - access_token_created_time >= token_live_time:
                    tg_web_data = await self.get_tg_web_data(proxy=proxy)
                    headers['Tl-Init-Data'] = tg_web_data
                    self.auth_token = tg_web_data
                    if self.logged:
                        self.refresh_token(session)
                    else:
                        self.login(session)
                    access_token_created_time = time()
                    token_live_time = randint(3500, 3600)

                if self.logged:
                    self.get_me(session)

                    attempt_play = settings.GAME_PLAY_EACH_ROUND
                    while attempt_play > 0:
                        attempt_play -= 1
                        wl = randint(1, 100)
                        if wl > 100:
                            try:
                                # print(headers)
                                res = session.post("https://api.bybitcoinsweeper.com/api/games/start", headers=headers)
                                res.raise_for_status()
                                game_data = res.json()
                                game_id = game_data['id']
                                bagcoins = game_data['rewards']['bagCoins']
                                bits = game_data['rewards']['bits']
                                gifts = game_data['rewards']['gifts']
                                logger.info(f"Successfully started game: <light-blue>{game_id}</light-blue>")
                                sleep_ = random.uniform(settings.TIME_PLAY_EACH_GAME[0], settings.TIME_PLAY_EACH_GAME[1])
                                logger.info(f"{self.session_name} | Wait <cyan>{sleep_}s</cyan> to complete game...")
                                await asyncio.sleep(sleep_)
                                payload = {
                                    "bagCoins": bagcoins,
                                    "bits": bits,
                                    "gameId": game_id,
                                    "gifts": gifts
                                }
                                head1 = {
                                    'Accept': '*/*',
                                    'Accept-Language': 'en-US',
                                    "Accept-Encoding": "gzip, deflate",
                                    "Access-Control-Request-Headers": "authorization,content-type,tl-init-data",
                                    "Access-Control-Request-Method": "POST",
                                    'Priority': "u=1, i",
                                    'Origin': 'https://bybitcoinsweeper.com',
                                    'Referer': 'https://bybitcoinsweeper.com/',
                                    'Sec-Fetch-Dest': 'empty',
                                    'Sec-Fetch-Mode': 'cors',
                                    'Sec-Fetch-Site': 'same-site',
                                    'Sec-Ch-Ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                                    'Sec-Ch-Ua-mobile': '?1',
                                    'Sec-Ch-Ua-platform': '"Android"',
                                    'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36',
                                }
                                res = session.options("https://api.bybitcoinsweeper.com/api/games/lose",
                                                      headers=head1)
                                res = session.post("https://api.bybitcoinsweeper.com/api/games/lose", headers=headers,json=payload)
                                if res.status_code == 201:
                                    logger.info(f"{self.session_name} | <red>Lose game: </red><cyan>{game_id}</cyan> <red>:(</red>")
                                    self.get_me(session)

                            except Exception as e:
                                print(res.text)
                                logger.warning(f"{self.session_name} | Unknown error while trying to play game: {e}")
                        else:
                            try:
                                # print(headers)
                                res = session.post("https://api.bybitcoinsweeper.com/api/games/start", headers=headers)
                                res.raise_for_status()
                                game_data = res.json()
                                started_at = game_data['createdAt']
                                game_id = game_data['id']
                                bagcoins = game_data['rewards']['bagCoins']
                                bits = game_data['rewards']['bits']
                                gifts = game_data['rewards']['gifts']
                                logger.info(f"Successfully started game: <light-blue>{game_id}</light-blue>")
                                sleep_ = random.uniform(settings.TIME_PLAY_EACH_GAME[0], settings.TIME_PLAY_EACH_GAME[1])
                                logger.info(f"{self.session_name} | Wait <cyan>{sleep_}s</cyan> to complete game...")
                                await asyncio.sleep(sleep_)
                                unix_time_started = datetime.strptime(started_at, '%Y-%m-%dT%H:%M:%S.%fZ')
                                unix_time_started = unix_time_started.replace(tzinfo=pytz.UTC)
                                unix_time_ms = int(unix_time_started.timestamp() * 1000)
                                timeplay = int(sleep_)
                                self.user_id += "v$2f1"
                                mr_pl = f"{game_id}-{unix_time_ms}"
                                lr_pl = round(random.uniform(285.01, 285.03), 5)
                                xr_pl = f"{self.user_id}-{mr_pl}"
                                kr_pl = f"{timeplay}-{game_id}"
                                _r = hmac.new(xr_pl.encode('utf-8'), kr_pl.encode('utf-8'), hashlib.sha256).hexdigest()
                                payload = {
                                    "bagCoins": bagcoins,
                                    "bits": bits,
                                    "gameId": game_id,
                                    "gameTime": timeplay,
                                    "gifts": gifts,
                                    "h": _r,
                                    "score": lr_pl
                                }
                                # print(lr_pl)
                                head1 = {
                                    'Accept': '*/*',
                                    'Accept-Language': 'en-US',
                                    "Accept-Encoding": "gzip, deflate",
                                    "Access-Control-Request-Headers": "authorization,content-type,tl-init-data",
                                    "Headers": "",
                                    "Access-Control-Request-Method": "POST",
                                    'Priority': "u=1, i",
                                    'Origin': 'https://bybitcoinsweeper.com',
                                    'Referer': 'https://bybitcoinsweeper.com/',
                                    'Sec-Fetch-Dest': 'empty',
                                    'Sec-Fetch-Mode': 'cors',
                                    'Sec-Fetch-Site': 'same-site',
                                    'Sec-Ch-Ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                                    'Sec-Ch-Ua-mobile': '?1',
                                    'Sec-Ch-Ua-platform': '"Android"',
                                    'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36',
                                }
                                res = session.options("https://api.bybitcoinsweeper.com/api/games/win",
                                                   headers=head1)
                                res = session.post("https://api.bybitcoinsweeper.com/api/games/win",
                                                   headers=headers,
                                                   json=payload)
                                if res.status_code == 201:
                                    logger.info(
                                        f"{self.session_name} | <green> Won game : </green><cyan>{game_id}</cyan> | Earned <yellow>{int(float(lr_pl))}</yellow>")
                                    # print(res.headers)
                                    self.get_me(session)
                                else:
                                    print(res.text)

                            except Exception as e:
                                print(res.text)
                                logger.warning(f"{self.session_name} | Unknown error while trying to play game: {e} - Sleep 20s")
                                await asyncio.sleep(20)

                        await asyncio.sleep(randint(10, 20))




                sleep_ = randint(500, 1000)
                logger.info(f"{self.session_name} | Sleep {sleep_}s...")
                await asyncio.sleep(sleep_)

            except InvalidSession as error:
                raise error

            except Exception as error:

                logger.error(f"{self.session_name} | Unknown error: {error}")
                await asyncio.sleep(delay=randint(60, 120))

async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        sleep_ = randint(1, 15)
        logger.info(f"{tg_client.name} | start after {sleep_}s")
        # await asyncio.sleep(sleep_)
        await Tapper(tg_client=tg_client).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")