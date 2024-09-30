import asyncio
import random
import sys
import traceback
from itertools import cycle
from time import time
from urllib.parse import unquote

import hmac
import hashlib
import aiohttp
from datetime import datetime

import requests
import pytz
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw import functions
from pyrogram.raw.functions.messages import RequestWebView
from bot.core.agents import generate_random_user_agent
from bot.config import settings

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from random import randint
import math

def value(i):
    return sum(ord(o) for o in list(i)) / 1e5


def calc(i, s, a, o, d, g):
    st = (10 * i + max(0, 1200 - 10 * s) + 2000) * (1 + o / a) / 10
    return math.floor(st) + value(g)


# mr = calc(45, 150, 54, 9, True, "17d26c4f-a453-4e29-b9bd-89c79a20d312")


class Tapper:
    def __init__(self, query: str, session_name: str, multi_thread):
        self.query = query
        self.session_name = session_name
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
        self.ref_id = "6624523270"
        self.refresh_token_ = None
        self.multi_thread = multi_thread

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy):
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
            return True
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")
            return False


    def login(self, session: requests.Session):
        try:
            head1 = {
                'Accept': '*/*',
                'Accept-Language': 'en,en-US;q=0.9,vi;q=0.8',
                "Accept-Encoding": "gzip, deflate, br",
                "Access-Control-Request-Headers": "content-type,tl-init-data",
                "Access-Control-Request-Method": "POST",
                'Origin': 'https://bybitcoinsweeper.com',
                'Referer': 'https://bybitcoinsweeper.com/',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site',
                'User-Agent': headers["User-Agent"],
            }
            res = session.options("https://api.bybitcoinsweeper.com/api/auth/login", headers=head1)

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
            self.access_token = user_data['accessToken']
            self.refresh_token_ = user_data['refreshToken']
            self.logged = True
        except Exception as e:
            traceback.print_exc()
            logger.error(f"{self.session_name} | Unknown error while trying to login: {e}")


    async def get_me(self, session):
        try:
            head1 = {
                'Accept': '*/*',
                'Accept-Language': 'en,en-US;q=0.9,vi;q=0.8',
                "Accept-Encoding": "gzip, deflate, br",
                'Connection': 'keep-alive',
                'Host': "api.bybitcoinsweeper.com",
                "Access-Control-Request-Headers": "authorization,tl-init-data",
                "Access-Control-Request-Method": "GET",
                'Origin': 'https://bybitcoinsweeper.com',
                'Referer': 'https://bybitcoinsweeper.com/',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site',
                'Sec-Ch-Ua': '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
                'Sec-Ch-Ua-mobile': '?1',
                'Sec-Ch-Ua-platform': '"Android"',
                'User-Agent': headers["User-Agent"]
            }
            res1 = session.options("https://api.bybitcoinsweeper.com/api/users/me",
                                  headers=head1)
            res = session.get("https://api.bybitcoinsweeper.com/api/users/me", headers=headers)
            if res.status_code == 200:
                user = res.json()
                self.user_id = user['id']
                logger.info(f"{self.session_name} | Balance: <light-yellow>{user['score']}</light-yellow>")
                return True
            else:
                logger.warning(f"{self.session_name} | <yellow>Get user info failed: {res.status_code} | {res.json()}</yellow>")
        except:
            return False

    def refresh_token(self, session: requests.Session):
        payload = {
            "refreshToken": str(self.refresh_token_)
        }
        res = session.post("https://api.bybitcoinsweeper.com/api/auth/refresh-token", headers=headers, json=payload)
        if res.status_code == 201:
            token = res.json()
            headers['Authorization'] = f"Bearer {token['accessToken']}"
            self.access_token = token['accessToken']
            self.refresh_token_ = token['refreshToken']
            logger.success(f"{self.session_name} | Refresh token successfully")

        else:
            logger.warning(f"{self.session_name} | <yellow>Refresh token failed: {res.text}</yellow>")


    async def run(self, proxy: str | None) -> None:
        access_token_created_time = 0
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        headers["User-Agent"] = generate_random_user_agent(device_type='android', browser_type='chrome')
        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)
        session = requests.Session()

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
        jwt_token_create_time = 0
        jwt_live_time = randint(850, 900)
        while True:
            try:
                if time() - jwt_token_create_time >= jwt_live_time:
                    if self.logged:
                        logger.info(f"{self.session_name} | Refreshing token...")
                        self.refresh_token(session)
                        jwt_token_create_time = time()
                        jwt_token_create_time = randint(850, 900)
                if time() - access_token_created_time >= token_live_time:
                    tg_web_data = self.query
                    headers['Tl-Init-Data'] = tg_web_data
                    self.auth_token = tg_web_data
                    self.login(session)
                    access_token_created_time = time()
                    token_live_time = randint(3500, 3600)
                self.logged = True
                if self.logged:
                    try:
                        await self.get_me(session)
                    except:
                        while True:
                            self.refresh_token(session)
                            if await self.get_me(session):
                                break

                    attempt_play = randint(settings.GAME_PLAY_EACH_ROUND[0], settings.GAME_PLAY_EACH_ROUND[1])
                    while attempt_play > 0:
                        attempt_play -= 1
                        wl = randint(1, 100)
                        if wl > 90:
                            try:
                                # print(headers)
                                res = session.post("https://api.bybitcoinsweeper.com/api/games/start", headers=headers, json={})
                                if res.status_code == 401:
                                    self.refresh_token(session)
                                    continue
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
                                    'Accept-Language': 'en,en-US;q=0.9,vi;q=0.8',
                                    "Accept-Encoding": "gzip, deflate, br",
                                    'Connection': 'keep-alive',
                                    'Host': "api.bybitcoinsweeper.com",
                                    "Access-Control-Request-Headers": "authorization,content-type,tl-init-data",
                                    "Access-Control-Request-Method": "POST",
                                    'Origin': 'https://bybitcoinsweeper.com',
                                    'Referer': 'https://bybitcoinsweeper.com/',
                                    'Sec-Fetch-Dest': 'empty',
                                    'Sec-Fetch-Mode': 'cors',
                                    'Sec-Fetch-Site': 'same-site',
                                    'Sec-Ch-Ua': '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
                                    'Sec-Ch-Ua-mobile': '?1',
                                    'Sec-Ch-Ua-platform': '"Android"',
                                    'User-Agent': headers["User-Agent"],
                                }
                                res = session.options("https://api.bybitcoinsweeper.com/api/games/lose",
                                                      headers=head1)
                                res = session.post("https://api.bybitcoinsweeper.com/api/games/lose", headers=headers ,json=payload)
                                if res.status_code == 201:
                                    logger.info(f"{self.session_name} | <red>Lose game: </red><cyan>{game_id}</cyan> <red>:(</red>")
                                    # await asyncio.sleep(random.uniform(0.5, 1.5))
                                    await self.get_me(session)
                                elif res.status_code == 401:
                                    self.refresh_token(session)
                                    continue

                            except Exception as e:
                                print(res.text)
                                logger.warning(f"{self.session_name} | Unknown error while trying to play game: {e}")
                        else:
                            try:
                                # print(headers)
                                head1 = {
                                    'Accept': '*/*',
                                    'Accept-Language': 'en,en-US;q=0.9,vi;q=0.8',
                                    "Accept-Encoding": "gzip, deflate, br",
                                    'Connection': 'keep-alive',
                                    'Host': "api.bybitcoinsweeper.com",
                                    "Access-Control-Request-Headers": "authorization,tl-init-data",
                                    "Access-Control-Request-Method": "POST",
                                    'Origin': 'https://bybitcoinsweeper.com',
                                    'Referer': 'https://bybitcoinsweeper.com/',
                                    'Sec-Fetch-Dest': 'empty',
                                    'Sec-Fetch-Mode': 'cors',
                                    'Sec-Fetch-Site': 'same-site',
                                    'Sec-Ch-Ua': '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
                                    'Sec-Ch-Ua-mobile': '?1',
                                    'Sec-Ch-Ua-platform': '"Android"',
                                    'User-Agent': headers["User-Agent"],
                                }
                                res1 = session.options("https://api.bybitcoinsweeper.com/api/games/start",
                                                      headers=head1)
                                res = session.post("https://api.bybitcoinsweeper.com/api/games/start", headers=headers, json={})
                                # print(http_client.headers)
                                if res.status_code == 401:
                                    self.refresh_token(session)
                                    continue
                                game_data = res.json()
                                # print(game_data)
                                started_at = game_data['createdAt']
                                game_id = game_data['id']
                                bagcoins = game_data['rewards']['bagCoins']
                                bits = game_data['rewards']['bits']
                                gifts = game_data['rewards']['gifts']
                                logger.info(f"Successfully started game: <light-blue>{game_id}</light-blue>")
                                sleep_ = randint(settings.TIME_PLAY_EACH_GAME[0], settings.TIME_PLAY_EACH_GAME[1])
                                logger.info(f"{self.session_name} | Wait <cyan>{sleep_}s</cyan> to complete game...")
                                await asyncio.sleep(sleep_)
                                unix_time_started = datetime.strptime(started_at, '%Y-%m-%dT%H:%M:%S.%fZ')
                                unix_time_started = unix_time_started.replace(tzinfo=pytz.UTC)
                                unix_time_ms = int(unix_time_started.timestamp() * 1000)
                                timeplay = sleep_
                                self.user_id += "v$2f1"
                                mr_pl = f"{game_id}-{unix_time_ms}"
                                lr_pl = calc(i=45,s=timeplay,a=54,o=9,d=True,g=game_id)
                                xr_pl = f"{self.user_id}-{mr_pl}"
                                kr_pl = f"{timeplay}-{game_id}"
                                _r = hmac.new(xr_pl.encode('utf-8'), kr_pl.encode('utf-8'), hashlib.sha256).hexdigest()
                                # print(lr_pl)
                                payload = {
                                    "bagCoins": bagcoins,
                                    "bits": bits,
                                    "gameId": game_id,
                                    "gameTime": timeplay,
                                    "gifts": gifts,
                                    "h": _r,
                                    "score": lr_pl
                                }
                                # print(payload)
                                # print(lr_pl)
                                head1 = {
                                    'Accept': '*/*',
                                    'Accept-Language': 'en,en-US;q=0.9,vi;q=0.8',
                                    "Accept-Encoding": "gzip, deflate, br",
                                    'Connection': 'keep-alive',
                                    'Host': "api.bybitcoinsweeper.com",
                                    "Access-Control-Request-Headers": "authorization,content-type,tl-init-data",
                                    "Access-Control-Request-Method": "POST",
                                    'Origin': 'https://bybitcoinsweeper.com',
                                    'Referer': 'https://bybitcoinsweeper.com/',
                                    'Sec-Fetch-Dest': 'empty',
                                    'Sec-Fetch-Mode': 'cors',
                                    'Sec-Fetch-Site': 'same-site',
                                    'Sec-Ch-Ua': '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
                                    'Sec-Ch-Ua-mobile': '?1',
                                    'Sec-Ch-Ua-platform': '"Android"',
                                    'User-Agent': headers["User-Agent"]
                                }
                                res = session.options("https://api.bybitcoinsweeper.com/api/games/win", headers=head1)

                                res = session.post("https://api.bybitcoinsweeper.com/api/games/win",
                                                   json=payload, headers=headers)

                                # print(res.text)
                                if res.status_code == 201:
                                    logger.info(
                                        f"{self.session_name} | <green> Won game : </green><cyan>{game_id}</cyan> | Earned <yellow>{int(lr_pl)}</yellow>")
                                    # print(res.headers)
                                    await self.get_me(session)
                                elif res.status_code == 401:
                                    self.refresh_token(session)
                                    continue

                            except Exception as e:
                                print(res.text)
                                logger.warning(f"{self.session_name} | Unknown error while trying to play game: {e} - Sleep 20s")
                                traceback.print_exc()
                                await asyncio.sleep(20)

                        await asyncio.sleep(randint(15, 25))

                if self.multi_thread:

                    sleep_ = randint(500, 1000)
                    logger.info(f"{self.session_name} | Sleep {sleep_}s...")
                    await asyncio.sleep(sleep_)
                else:
                    await http_client.close()
                    session.close()
                    break

            except InvalidSession as error:
                raise error

            except Exception as error:
                traceback.print_exc()
                logger.error(f"{self.session_name} | Unknown error: {error}")
                await asyncio.sleep(delay=randint(60, 120))



async def run_query_tapper(query: str, name: str, proxy: str | None):
    try:
        sleep_ = randint(1, 15)
        logger.info(f" start after {sleep_}s")
        await asyncio.sleep(sleep_)
        await Tapper(query=query, session_name=name, multi_thread=True).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"Invalid Query: {query}")

async def run_query_tapper1(querys: list[str], proxies):
    proxies_cycle = cycle(proxies) if proxies else None
    name = "Account"

    while True:
        i = 0
        for query in querys:
            try:
                await Tapper(query=query,session_name=f"{name} {i}",multi_thread=False).run(next(proxies_cycle) if proxies_cycle else None)
            except InvalidSession:
                logger.error(f"Invalid Query: {query}")

            sleep_ = randint(settings.DELAY_EACH_ACCOUNT[0], settings.DELAY_EACH_ACCOUNT[1])
            logger.info(f"Sleep {sleep_}s...")
            await asyncio.sleep(sleep_)

        sleep_ = randint(500, 700)
        logger.info(f"<red>Sleep {sleep_}s...</red>")
        await asyncio.sleep(sleep_)
