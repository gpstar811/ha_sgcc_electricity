import hashlib
import base64
import io
import logging
import os
import typing as typ

import requests


def _balance_threshold() -> float:
    return float(os.getenv("BALANCE", 10.0))


def _should_notify(balance: float) -> bool:
    threshold = _balance_threshold()
    logging.info("检查电费余额，低于 %s 元时将发送通知", threshold)
    return balance < threshold


def _post_wework(webhook: str, payload: dict) -> bool:
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        if resp.status_code != 200:
            logging.warning("企业微信推送 HTTP 失败: %s %s", resp.status_code, resp.text[:200])
            return False
        data = resp.json()
        if data.get("errcode", 0) != 0:
            logging.warning("企业微信推送返回错误: %s", data)
            return False
        return True
    except Exception as exc:
        logging.warning("企业微信推送异常: %s", exc)
        return False


class PushplusNotify(typ.NamedTuple):

    def __call__(self, user_id, balance):
        if not _should_notify(balance):
            return False
        tokens = os.getenv("PUSHPLUS_TOKEN", "").split(",")
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            title = "电费余额不足提醒"
            content = f"您用户号{user_id}的当前电费余额为：{balance}元，请及时充值。"
            url = f"http://www.pushplus.plus/send?token={token}&title={title}&content={content}"
            resp = requests.get(url, timeout=10)
            logging.info("已发送 PushPlus 余额提醒: 户号=%s 余额=%s", user_id, balance)
            return resp.status_code == 200
        return False


class UrlPushNotify(typ.NamedTuple):

    def __call__(self, user_id, balance):
        if not _should_notify(balance):
            return False
        url = os.getenv("PUSH_URL", "").strip()
        if not url:
            logging.warning("PUSH_URL 未配置")
            return False
        resp = requests.post(url, json={"user_id": user_id, "balance": balance}, timeout=10)
        logging.info("已发送 URL 余额提醒: 户号=%s 余额=%s", user_id, balance)
        return resp.status_code == 200


class WeworkNotify(typ.NamedTuple):
    """企业微信群机器人 webhook 余额提醒。"""

    def __call__(self, user_id, balance):
        if not _should_notify(balance):
            return False
        webhook = os.getenv("WEWORK_WEBHOOK_URL", "").strip()
        if not webhook:
            logging.warning("WEWORK_WEBHOOK_URL 未配置")
            return False
        threshold = _balance_threshold()
        content = (
            "**电费余额不足提醒**\n"
            f"> 户号：<font color=\"comment\">{user_id}</font>\n"
            f"> 当前余额：<font color=\"warning\">{balance} 元</font>\n"
            f"> 提醒阈值：{threshold} 元\n"
            "请及时登录国网 APP 或网站充值。"
        )
        payload = {"msgtype": "markdown", "markdown": {"content": content}}
        ok = _post_wework(webhook, payload)
        if ok:
            logging.info("已发送企业微信余额提醒: 户号=%s 余额=%s", user_id, balance)
        return ok


class UrlLoginQrCodeNotify(typ.NamedTuple):

    def __call__(self, qrcode) -> bool:
        url = os.getenv("PUSH_QRCODE_URL", "").strip()
        if not url:
            return False
        files = {"file": ("qrcode.png", io.BytesIO(qrcode), "image/png")}
        resp = requests.post(url, files=files, timeout=15)
        logging.info("已推送二维码到自定义 URL")
        return resp.status_code == 200


class WeworkQrCodeNotify(typ.NamedTuple):
    """企业微信群机器人推送登录二维码（image 类型）。"""

    def __call__(self, qrcode) -> bool:
        webhook = os.getenv("WEWORK_WEBHOOK_URL", "").strip()
        if not webhook:
            return False
        if isinstance(qrcode, str):
            qrcode = qrcode.encode("utf-8")
        image_md5 = hashlib.md5(qrcode).hexdigest()
        image_base64 = base64.b64encode(qrcode).decode("ascii")
        payload = {
            "msgtype": "image",
            "image": {"base64": image_base64, "md5": image_md5},
        }
        ok = _post_wework(webhook, payload)
        if ok:
            logging.info("已推送登录二维码到企业微信")
        return ok


def get_qrcode_notifier():
    """按配置选择二维码推送方式。"""
    push_type = os.getenv("PUSH_TYPE", "none").lower()
    if os.getenv("PUSH_QRCODE_URL", "").strip():
        return UrlLoginQrCodeNotify()
    if push_type == "wework" and os.getenv("WEWORK_WEBHOOK_URL", "").strip():
        return WeworkQrCodeNotify()
    return None
