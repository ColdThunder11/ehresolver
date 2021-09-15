from hoshino import Service, priv
from hoshino.typing import CQEvent
from hoshino.priv import *

from bs4 import BeautifulSoup
from os import path

import json
import httpx

sv = Service("eh解析")

ex_config: dict = None
tag_words: dict = None

with open(path.join(path.dirname(__file__), "config.json"), "r", encoding="utf8")as fp:
    ex_config = json.load(fp)
with open(path.join(path.dirname(__file__), "tag_matcher.json"), "r", encoding="utf8")as fp:
    tag_words = json.load(fp)

proxies = ex_config["proxy"]

ex_headers = headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Host": "exhentai.org",
    "Origin": "https://exhentai.org",
    "Referer": "https://exhentai.org/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": ex_config["ua"],
    "Cookie": ex_config["cookie"]
}


def get_raw_msg(msg: str):
    return msg.replace("&amp;", "&").replace("&#91;", "[").replace("&#93;", "]").replace("&#44;", ",")


async def get_bz_link(name: str):
    get_para = {
        "f_search": name
    }
    sv.logger.info(f"正在e站内搜素{name}")
    async with httpx.AsyncClient(proxies=proxies, timeout=20) as client:
        res = await client.get(url="https://exhentai.org/", params=get_para,
                               headers=headers)
    soup = BeautifulSoup(res.text, "lxml")
    search_results = soup.select(".gl3c")
    true_link: str = None
    for res_item in search_results:
        true_link = res_item.select_one("a").get("href")
        break
    return true_link


async def get_bz_info(link: str):
    sv.logger.info(f"正在解析{link}")
    async with httpx.AsyncClient(proxies=proxies, timeout=20) as client:
        res = await client.get(url=link, headers=headers)
    post_date: str = None
    language: str = None
    page_length: str = None
    favorite: str = None
    tag_list = []
    bz_page_bs = BeautifulSoup(res.text, "lxml")
    basic_info_div = bz_page_bs.select_one("#gdd")
    # print(basic_info_div)
    basic_info_trs = basic_info_div.select("tr")
    for basic_info_tr in basic_info_trs:
        tr_text = basic_info_tr.select_one(".gdt1").text
        if tr_text == "Posted:":
            post_date = basic_info_tr.select_one(".gdt2").text
        elif tr_text == "Language:":
            language = basic_info_tr.select_one(".gdt2").text.split(" ")[0]
        elif tr_text == "Length:":
            page_length = basic_info_tr.select_one(
                ".gdt2").text.replace(" pages", "")
        elif tr_text == "Favorited:":
            favorite = basic_info_tr.select_one(
                ".gdt2").text.replace(" times", "")
    rating_count = bz_page_bs.select_one("#rating_count").text
    rating_avg = bz_page_bs.select_one(
        "#rating_label").text.replace("Average: ", "")
    tag_list_div = bz_page_bs.select_one("#taglist")
    tags_trs = tag_list_div.select("tr")
    for tags_item in tags_trs:
        if tags_item.select_one(".tc").text == "male:":
            tags = tags_item.select("a")
            for tag in tags:
                tag_list.append(f"m:{tag.text}")
        elif tags_item.select_one(".tc").text == "female:":
            tags = tags_item.select("a")
            for tag in tags:
                tag_list.append(f"f:{tag.text}")
        else:
            tags = tags_item.select("a")
            for tag in tags:
                tag_list.append(tag.text)
    ret_dict = {
        "post_date": post_date,
        "language": language,
        "page_length": page_length,
        "favorite": favorite,
        "rating_count": rating_count,
        "rating_avg": rating_avg,
        "tag_list": tag_list,
    }
    return ret_dict


def get_msg_from_bz_info(link: str, info: dict):
    msg = f"监测到本子\n{link.split('.org/')[1]}\n发布日期:{info['post_date']}\n页数:{info['page_length']}\n收藏数:{info['favorite']}\n评分:{info['rating_avg']} 共{info['rating_count']}人"
    matcher_group = tag_words["matcher"]
    for tag in info["tag_list"]:
        for matcher in matcher_group:
            if tag in matcher["tags"]:
                msg += f"\n{matcher['words']}"
    return msg


@sv.on_keyword(("[中国翻訳]", "[Chinese]"))
async def try_search_bz_info(bot, ev: CQEvent):
    try:
        link = await get_bz_link(get_raw_msg(ev.raw_message))
        if not link:
            await bot.send(ev, "检测到了疑似本子但是没有在e站搜索到")
            return
        info = await get_bz_info(link)
        await bot.send(ev, get_msg_from_bz_info(link, info))
    except:
        return


@sv.on_prefix(("https://exhentai.org", "https://e-hentai.org", "exhentai.org", "e-hentai.org"))
async def try_reslove_bz(bot, ev: CQEvent):
    try:
        info = await get_bz_info(ev.raw_message)
        await bot.send(ev, get_msg_from_bz_info(ev.raw_message, info))
    except:
        return
