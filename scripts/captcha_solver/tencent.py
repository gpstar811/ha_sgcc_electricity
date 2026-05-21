import json
import logging
import os
import random
import re
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from captcha_solver.image import PointClickImageSolver, capture_element_image


class TencentCaptchaHandler:
    """Tencent point-click captcha handler for 95598 login."""

    POINT_CLICK_MAX_REFRESHES = 3

    def __init__(self, trace_dir=None):
        if trace_dir is None:
            from const import get_data_dir
            trace_dir = Path(get_data_dir()) / 'pages'
        self._trace_dir = Path(trace_dir)
        self._trace_dir.mkdir(parents=True, exist_ok=True)
        self._point_click_solver = PointClickImageSolver()
        self.point_click_max_refreshes = int(
            os.getenv("CAPTCHA_POINT_CLICK_MAX_REFRESHES", self.POINT_CLICK_MAX_REFRESHES)
        )

    def has_captcha(self, driver) -> bool:
        try:
            return self._get_visible_widget(driver) is not None
        except Exception:
            return False

    @staticmethod
    def _get_visible_widget(driver):
        try:
            return driver.execute_script(
                """
                const selectors = [
                  '#tCaptchaDyContent',
                  '.tencent-captcha-dy__warp',
                  '.tencent-captcha-dy__wrapper',
                  '.tencent-captcha__wrapper',
                  '.tencent-captcha-dy__body-wrap',
                  '.tencent-captcha-dy__image-area',
                  '.tencent-captcha-dy__verify-bg',
                  '.tencent-captcha-dy__verify-bg-img',
                  '.tencent-captcha-dy__verify-slider-area',
                  '.tencent-captcha-dy__slider-groove',
                  '[class*="tencent-captcha-dy__content"]'
                ];
                const visible = (el, doc) => {
                  const rect = el.getBoundingClientRect();
                  const style = doc.defaultView.getComputedStyle(el);
                  const inViewport = rect.bottom > 0 && rect.right > 0
                    && rect.top < doc.defaultView.innerHeight && rect.left < doc.defaultView.innerWidth;
                  return rect.width > 40 && rect.height > 40
                    && style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && inViewport;
                };
                const search = (doc) => {
                  const nodes = selectors.flatMap((selector) => Array.from(doc.querySelectorAll(selector)));
                  const found = nodes.find((el) => visible(el, doc));
                  if (found) return found;
                  const frames = Array.from(doc.querySelectorAll('iframe,frame'));
                  for (const frame of frames) {
                    try {
                      const child = frame.contentDocument;
                      if (child) {
                        const nested = search(child);
                        if (nested) return nested;
                      }
                    } catch (err) {}
                  }
                  return null;
                };
                return search(document);
                """
            )
        except Exception:
            return None

    def get_visible_descendant(self, driver, selectors, min_width=20, min_height=20):
        try:
            widget = self._get_visible_widget(driver)
            if not widget:
                return None
            return driver.execute_script(
                """
                const root = arguments[0];
                const selectors = arguments[1];
                const minWidth = arguments[2];
                const minHeight = arguments[3];
                const search = (node) => {
                  const doc = node.ownerDocument || node;
                  const nodes = selectors.flatMap((selector) => Array.from(node.querySelectorAll(selector)));
                  const visible = nodes
                    .filter((el) => {
                      const rect = el.getBoundingClientRect();
                      const style = doc.defaultView.getComputedStyle(el);
                      const inViewport = rect.bottom > 0 && rect.right > 0
                        && rect.top < doc.defaultView.innerHeight && rect.left < doc.defaultView.innerWidth;
                      return rect.width >= minWidth
                        && rect.height >= minHeight
                        && style.display !== 'none'
                        && style.visibility !== 'hidden'
                        && inViewport;
                    })
                    .sort((a, b) => {
                      const ar = a.getBoundingClientRect();
                      const br = b.getBoundingClientRect();
                      return (br.width * br.height) - (ar.width * ar.height);
                    });
                  if (visible.length > 0) return visible[0];
                  const frames = Array.from(node.querySelectorAll('iframe,frame'));
                  for (const frame of frames) {
                    try {
                      const child = frame.contentDocument;
                      if (child) {
                        const nested = search(child);
                        if (nested) return nested;
                      }
                    } catch (err) {}
                  }
                  return null;
                };
                return search(root);
                """,
                widget,
                selectors,
                min_width,
                min_height,
            )
        except Exception:
            return None

    def wait_for_captcha(self, driver, timeout=15) -> bool:
        """等待验证码容器出现。"""
        try:
            WebDriverWait(driver, timeout).until(lambda d: self.has_captcha(d))
            return True
        except Exception:
            return False

    def get_info(self, driver):
        try:
            return driver.execute_script(
                """
                const textOf = (selector) => {
                  const docs = [document];
                  const seen = new Set();
                  while (docs.length) {
                    const doc = docs.pop();
                    if (!doc || seen.has(doc)) continue;
                    seen.add(doc);
                    const els = doc.querySelectorAll(selector);
                    for (const el of els) {
                      if (el.offsetParent !== null) {
                        return (el.innerText || el.textContent || '').trim();
                      }
                    }
                    Array.from(doc.querySelectorAll('iframe,frame')).forEach((frame) => {
                      try {
                        if (frame.contentDocument) docs.push(frame.contentDocument);
                      } catch (err) {}
                    });
                  }
                  return '';
                };
                const exists = (selector) => {
                  const docs = [document];
                  const seen = new Set();
                  while (docs.length) {
                    const doc = docs.pop();
                    if (!doc || seen.has(doc)) continue;
                    seen.add(doc);
                    const els = doc.querySelectorAll(selector);
                    for (const el of els) {
                      if (el.offsetParent !== null) return true;
                    }
                    Array.from(doc.querySelectorAll('iframe,frame')).forEach((frame) => {
                      try {
                        if (frame.contentDocument) docs.push(frame.contentDocument);
                      } catch (err) {}
                    });
                  }
                  return false;
                };
                const prompt =
                  textOf('.tencent-captcha-dy__header-text') ||
                  textOf('.tencent-captcha-dy__question') ||
                  textOf('.tencent-captcha-dy__title') ||
                  textOf('.tencent-captcha__title') ||
                  textOf('.tencent-captcha-dy__sub-title') ||
                  textOf('.tencent-captcha__sub-title') ||
                  '';

                if (/拖动|拼图|滑块/i.test(prompt)) {
                  return { mode: 'slider', prompt };
                }
                if (exists('.tencent-captcha-dy__slider-groove') ||
                    exists('.tencent-captcha-dy__verify-slider-area')) {
                  return { mode: 'slider', prompt };
                }

                const hasPointClick =
                  /依次点击|顺序点击|点击下图|文字点选|请点击|点击/i.test(prompt) ||
                  exists('.tencent-captcha-dy__click-type-wrap') ||
                  exists('.tencent-captcha-dy__click-word') ||
                  exists('.tencent-captcha-dy__point-area') ||
                  exists('.tencent-captcha-dy__word-content') ||
                  exists('.tencent-captcha-dy__header-answer img') ||
                  exists('.tencent-captcha-dy__header-answer');
                if (hasPointClick) {
                  return { mode: 'point_click', prompt };
                }
                return { mode: 'unknown', prompt };
                """
            ) or {"mode": "unknown", "prompt": ""}
        except Exception as exc:
            return {"mode": "unknown", "prompt": "", "error": str(exc)}

    def refresh_captcha(self, driver) -> bool:
        """多策略刷新验证码（对齐上游）。"""
        if self._click_point_click_refresh(driver):
            return True
        try:
            btn = driver.find_element(By.CSS_SELECTOR, ".tencent-captcha-dy__footer-icon--refresh")
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                logging.info("已通过标准刷新按钮刷新验证码")
                time.sleep(random.uniform(0.8, 1.4))
                return True
        except Exception:
            pass
        try:
            driver.execute_script(
                """
                var els = document.querySelectorAll('[class*="refresh"], [class*="footer-icon"]');
                for (var i = 0; i < els.length; i++) {
                    if (els[i].offsetParent !== null && els[i].getBoundingClientRect().width > 5) {
                        els[i].click();
                        return true;
                    }
                }
                return false;
                """
            )
            logging.info("已通过 JS 回退方式刷新验证码")
            time.sleep(random.uniform(0.8, 1.4))
            return True
        except Exception:
            return False

    def _click_point_click_refresh(self, driver) -> bool:
        try:
            widget = self._get_visible_widget(driver)
            if not widget:
                return False
            refresh = driver.execute_script(
                """
                const root = arguments[0];
                const keywords = arguments[1];
                const visible = (el, doc) => {
                  if (!el) return false;
                  const rect = el.getBoundingClientRect();
                  const style = doc.defaultView.getComputedStyle(el);
                  return rect.width >= 10 && rect.height >= 10
                    && style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && style.opacity !== '0';
                };
                const textOf = (el) => {
                  return [
                    el.innerText || '', el.textContent || '',
                    el.getAttribute('aria-label') || '',
                    el.className || '', el.id || ''
                  ].join(' ').trim();
                };
                const isKeywordMatch = (el) => keywords.some((k) => textOf(el).includes(k));
                const clickElement = (el) => {
                  if (!el) return false;
                  const target = el.closest('button,[role="button"],a,[class*="btn"],[class*="refresh"]') || el;
                  try { target.click(); return true; } catch (err) { return false; }
                };
                const selectors = ['button','[role="button"]','a','[class*="btn"]','[class*="refresh"]','svg','span','div'];
                const nodes = selectors.flatMap((s) => Array.from((root.ownerDocument || document).querySelectorAll(s)));
                const keywordNode = nodes.find((el) => visible(el, root.ownerDocument || document) && isKeywordMatch(el));
                if (keywordNode && clickElement(keywordNode)) return true;
                const rect = root.getBoundingClientRect();
                const doc = root.ownerDocument || document;
                const x = Math.max(rect.right - 22, rect.left + 1);
                const y = Math.max(rect.bottom - 22, rect.top + 1);
                const point = doc.elementFromPoint(x, y);
                if (!point) return false;
                return clickElement(point.closest('button,[role="button"],a,[class*="btn"],[class*="refresh"]') || point);
                """,
                widget,
                ["刷新", "换一张", "重试", "换图", "看不清", "refresh", "reload", "retry"],
            )
            if refresh:
                logging.info("Clicked point-click captcha refresh button.")
                time.sleep(random.uniform(0.8, 1.4))
                return True
        except Exception as exc:
            logging.info("Failed to click refresh button: %s", exc)
        return False

    @staticmethod
    def _load_image_from_element(driver, element) -> Image.Image:
        """优先从 img src 下载原图，截图作为回退（Docker headless 更清晰）。"""
        src = (element.get_attribute("src") or "").strip()
        if src.startswith("http"):
            try:
                resp = requests.get(src, timeout=15)
                if resp.status_code == 200 and resp.content:
                    return Image.open(BytesIO(resp.content)).convert("RGB")
            except Exception as exc:
                logging.info("从 URL 下载验证码图片失败，回退截图: %s", exc)
        elif src.startswith("data:image"):
            try:
                import base64

                encoded = src.split(",", 1)[1]
                return Image.open(BytesIO(base64.b64decode(encoded))).convert("RGB")
            except Exception as exc:
                logging.info("解析 data URI 验证码图片失败，回退截图: %s", exc)
        return Image.open(BytesIO(capture_element_image(driver, element))).convert("RGB")

    @staticmethod
    def _click_with_offset(driver, element, x_offset: int, y_offset: int) -> None:
        try:
            ActionChains(driver).move_to_element_with_offset(
                element, x_offset, y_offset
            ).pause(random.uniform(0.05, 0.15)).click().perform()
        except Exception:
            driver.execute_script(
                "var r = arguments[0].getBoundingClientRect();"
                "var cx = r.left + r.width/2 + arguments[1];"
                "var cy = r.top + r.height/2 + arguments[2];"
                "var el = document.elementFromPoint(cx, cy);"
                "if (el) {"
                "  ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(t){"
                "    el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, clientX:cx, clientY:cy}));"
                "  });"
                "}",
                element,
                x_offset,
                y_offset,
            )

    def _try_click_solution(self, driver, bg_element, bg_image, points) -> bool:
        bg_rect = bg_element.rect
        x_scale = bg_rect["width"] / max(bg_image.width, 1)
        y_scale = bg_rect["height"] / max(bg_image.height, 1)
        for x, y, _score in points:
            x_offset = int((x * x_scale) - (bg_rect["width"] / 2))
            y_offset = int((y * y_scale) - (bg_rect["height"] / 2))
            self._click_with_offset(driver, bg_element, x_offset, y_offset)
            time.sleep(random.uniform(0.25, 0.55))

        try:
            confirm = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".tencent-captcha-dy__verify-confirm-btn")
                )
            )
            WebDriverWait(driver, 5).until(
                lambda _d: "disabled" not in (confirm.get_attribute("class") or "")
            )
            driver.execute_script("arguments[0].click();", confirm)
        except Exception:
            logging.info("Confirm button not found, points may auto-submit.")

        time.sleep(random.uniform(1.5, 2.5))
        return not self.has_captcha(driver)

    def solve_point_click_captcha(self, driver, wait_time=60) -> bool:
        """Solve a Tencent point-click captcha. Returns True on success."""
        answer_image = None
        bg_image = None
        try:
            info = self.get_info(driver)
            logging.info("Tencent captcha detected, mode=%s, prompt=%s", info.get("mode"), info.get("prompt", ""))

            if info.get("mode") != "point_click":
                logging.info("Captcha is not point_click mode, cannot solve locally.")
                return False

            for attempt in range(self.point_click_max_refreshes + 1):
                try:
                    answer_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".tencent-captcha-dy__header-answer img")
                        )
                    )
                    bg_element = WebDriverWait(driver, 5).until(
                        lambda _d: self.get_visible_descendant(
                            _d,
                            [
                                ".tencent-captcha-dy__point-area",
                                ".tencent-captcha-dy__click-type-wrap",
                                ".tencent-captcha-dy__verify-bg-img",
                                ".tencent-captcha-dy__verify-bg",
                                ".tencent-captcha-dy__image-area",
                            ],
                            min_width=80,
                            min_height=80,
                        )
                        or False
                    )
                except Exception as exc:
                    logging.info("Point-click elements not ready on attempt %s: %s", attempt, exc)
                    if attempt < self.point_click_max_refreshes and self._click_point_click_refresh(driver):
                        continue
                    return False

                answer_image = self._point_click_solver.trim_nonwhite_border(
                    self._load_image_from_element(driver, answer_element),
                    threshold=245,
                    padding=4,
                )
                bg_image = self._load_image_from_element(driver, bg_element)

                # Save debug images
                self._save_debug_images(answer_image, bg_image, f"attempt_{attempt}")

                solution_limit = int(os.getenv("CAPTCHA_LOCAL_SOLUTION_CANDIDATES", "3"))
                solutions = self._point_click_solver.ranked_solutions_from_images(
                    answer_image,
                    bg_image,
                    limit=solution_limit,
                    min_average_score=float(os.getenv("CAPTCHA_MIN_AVG_SCORE", "0.38")),
                    min_point_score=float(os.getenv("CAPTCHA_MIN_POINT_SCORE", "0.18")),
                    min_score_gap=float(os.getenv("CAPTCHA_MIN_SCORE_GAP", "0.003")),
                )

                if not solutions:
                    logging.info("No confident solution found on attempt %s.", attempt)
                    if attempt < self.point_click_max_refreshes and self._click_point_click_refresh(driver):
                        continue
                    return False

                for solution_index, (average_score, points) in enumerate(solutions, start=1):
                    logging.info(
                        "Point-click solution #%s: points=%s average_score=%.3f",
                        solution_index,
                        [(round(x, 1), round(y, 1), round(s, 3)) for x, y, s in points],
                        average_score,
                    )
                    if self._try_click_solution(driver, bg_element, bg_image, points):
                        logging.info(
                            "Point-click captcha solved on attempt %s solution #%s.",
                            attempt,
                            solution_index,
                        )
                        self._save_debug_images(answer_image, bg_image, f"success_{attempt}_{solution_index}")
                        return True
                    logging.info(
                        "Point-click solution #%s failed on attempt %s, trying next candidate.",
                        solution_index,
                        attempt,
                    )

                logging.info("All point-click candidates failed on attempt %s.", attempt)
                self._save_debug_images(answer_image, bg_image, f"failed_{attempt}")
                if attempt < self.point_click_max_refreshes and self._click_point_click_refresh(driver):
                    continue
                return False

            return False
        except Exception as exc:
            logging.warning("Point-click captcha solver failed: %s", exc)
            if answer_image is not None and bg_image is not None:
                self._save_debug_images(answer_image, bg_image, "exception")
            return False

    def _human_delay(self):
        time.sleep(random.uniform(0.8, 1.4))

    def _save_debug_images(self, answer_image, bg_image, suffix: str) -> None:
        try:
            self._trace_dir.mkdir(parents=True, exist_ok=True)
            answer_path = self._trace_dir / f"captcha_answer_{suffix}.png"
            bg_path = self._trace_dir / f"captcha_bg_{suffix}.png"
            answer_image.save(answer_path)
            bg_image.save(bg_path)
            logging.info("Saved captcha debug images to %s and %s", answer_path, bg_path)
            # Save diagnostics
            report = self._point_click_solver.get_last_diagnostics()
            if report:
                report_path = self._trace_dir / f"captcha_report_{suffix}.json"
                report_path.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        except Exception as exc:
            logging.debug("Failed to save debug images: %s", exc)
