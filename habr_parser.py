import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime
from time import sleep
from random import randint
from PyQt5.QtCore import QObject, pyqtSignal


class HabrParser(QObject):
    parsing_finished = pyqtSignal(list, list)
    progress_updated = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.base_url = "https://habr.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        self.stop_parsing = False
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("HabrParser")

    def parse_habr(self, start_date, end_date, max_articles=None):
        self.stop_parsing = False
        all_articles = []
        all_tags = []
        page = 1

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            self.logger.error(f"Ошибка формата даты: {e}")
            self.error_occurred.emit(f"Ошибка формата даты: {e}")
            return

        while (not self.stop_parsing and
               (max_articles is None or len(all_articles) < max_articles)):

            try:
                self.logger.info(f"Парсинг страницы {page}...")
                articles, tags, has_content = self.parse_page(page, start_date, end_date)

                if not has_content:
                    if page > 50:
                        break
                    self.logger.info(f"На этой странице нет подходящих статей от {start_date} до {end_date}")
                    page += 1
                    # sleep(randint(2, 5))
                    continue

                retry_count = 0

                if max_articles is not None:
                    remaining = max_articles - len(all_articles)
                    if remaining <= 0:
                        break
                    articles = articles[:remaining]
                    tags = tags[:remaining]

                all_articles.extend(articles)
                all_tags.extend(tags)

                if max_articles:
                    progress = min(99, int((len(all_articles) / max_articles * 100)))
                else:
                    progress = min(90, int((page / 100) * 90))
                self.progress_updated.emit(progress)

                if articles:
                    earliest_date = min(art[0] for art in articles)
                    if earliest_date < start_date:
                        break

                page += 1
                sleep(randint(1, 3))

            except Exception as e:
                self.logger.error(f"Ошибка при парсинге страницы {page}: {str(e)}")
                self.error_occurred.emit(f"Ошибка при парсинге страницы {page}: {str(e)}")
                sleep(randint(5, 10))
                continue

        self.progress_updated.emit(100)
        self.logger.info(f"Парсинг завершен. Найдено {len(all_articles)} статей.")
        self.parsing_finished.emit(all_articles, all_tags)

    def parse_page(self, page_num, start_date, end_date):
        try:
            url = f"{self.base_url}/ru/all/page{page_num}/"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            if "404 Not Found" in response.text:
                return [], [], False

            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.find_all("article", class_="tm-articles-list__item")

            if not articles:
                return [], [], False

            page_data = []
            page_tags = []
            has_valid_content = False

            for article in articles:
                if self.stop_parsing:
                    break

                try:
                    date_tag = article.find("time")
                    if not date_tag:
                        continue

                    article_date = date_tag["datetime"].split("T")[0]
                    if article_date < start_date or article_date > end_date:
                        continue

                    title_tag = article.find("h2")
                    if not title_tag:
                        continue

                    title = title_tag.text.strip()
                    link = self.base_url + title_tag.find("a")["href"]

                    author = article.find("a", class_="tm-user-info__username")
                    author = author.text.strip() if author else "Нет автора"

                    rating = article.find("span", class_="tm-votes-meter__value")
                    rating = rating.text.strip() if rating else "0"

                    comments = article.find("span", class_="tm-article-comments-counter-link__value")
                    comments = comments.text.strip() if comments else "0"

                    description, tags = self.get_article_data(link)

                    page_data.append([article_date, title, link, author, rating, comments, tags, description])
                    page_tags.append(tags)
                    has_valid_content = True

                except Exception as e:
                    self.logger.warning(f"Ошибка обработки статьи: {str(e)}")
                    continue

            return page_data, page_tags, has_valid_content

        except requests.RequestException as e:
            self.logger.error(f"Ошибка запроса для страницы {page_num}: {str(e)}")
            return [], [], False
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при парсинге страницы {page_num}: {str(e)}")
            return [], [], False

    def get_article_data(self, article_url):
        try:
            response = self.session.get(article_url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            body = soup.find("div", class_="tm-article-body")
            if body:
                description = ' '.join(p.text.strip() for p in body.find_all("p")[:5] if p.text.strip())
                description = (description[:497] + '...') if len(description) > 500 else description
            else:
                description = "Нет описания"

            tags = []
            tags_container = soup.find("div", class_="tm-article-presenter__meta-list")
            if tags_container:
                tags = [a.text.strip() for a in tags_container.find_all("a", class_="tm-tags-list__link")][:5]

            return description, ", ".join(tags)

        except requests.RequestException as e:
            self.logger.warning(f"Ошибка запроса для статьи {article_url}: {str(e)}")
            return "Ошибка загрузки", ""
        except Exception as e:
            self.logger.warning(f"Неожиданная ошибка при обработке статьи {article_url}: {str(e)}")
            return "Ошибка обработки", ""

    def stop(self):
        self.stop_parsing = True
        self.logger.info("Получен запрос на остановку парсинга")
