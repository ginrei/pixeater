import fake_useragent
import json
import os
from io import BytesIO
import requests
import re
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.parse import urlparse
from PIL import Image

XORIGIN_POLICY_MODERATE = "moderate"
XORIGIN_POLICY_RESTRICT = "restrict"

config_file = open('config.json', 'r')
config_json = json.load(config_file)

SITE_URLS  = config_json['site_urls']
EXTENSIONS = config_json['extensions']
MIN_WIDTH  = config_json['min_size']['width']
MIN_HEIGHT = config_json['min_size']['height']
MAX_DEPTH  = config_json['max_depth']
XORIGIN_POLICY = config_json['xorigin_policy']


class Crawler(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.headers = {'User-Agent': fake_useragent.UserAgent().chrome}
        self.current_location = ''
        self.current_origin = ''
        self.current_moderate_origin = ''
        self.visited = []
        self.links = []
        self.xorigin_policy = ''

        self.min_height = 0
        self.min_width = 0

        self.save_dir = os.path.dirname(os.path.abspath(__file__)) + '/download'

    def set_min_width_height(self, min_width, min_height):
        self.min_width  = min_width
        self.min_height = min_height

    def crawl(self, site_urls, max_depth, xorigin_policy, depth = 0):
        self.xorigin_policy = xorigin_policy

        print('CRAWL DEPTH ' + str(depth) + ' START-------------')
        print('URLS:')
        print(site_urls)

        for site_url in site_urls:

            print('\nGET: ' + site_url)

            response = requests.get(site_url, headers = self.headers)

            # use response.url as current location. not site_url.
            # why: site_url may vary from the actual URL of the page, when 301 redirect occured.
            if depth == 0:
                self.current_location = response.url
                self.current_origin = urlparse(response.url).netloc
                self.current_moderate_origin = re.search('[^\.]+\.[^\.]+$', self.current_origin).group(0)
            self.visited.append(response.url)

            self.current_location = response.url

            if response.status_code == 404:
                continue

            # TODO: merge text image routing

            if re.match('text\/', response.headers['content-type']):
                save_file_name = re.sub('^\/', '', urlparse(response.url).path)
                if save_file_name.endswith('/') or save_file_name == '':
                    save_file_name = save_file_name + 'index.html'
                save_file_path = os.path.join(self.save_dir, save_file_name)

                if not os.path.exists(os.path.dirname(save_file_path)):
                    os.makedirs(os.path.dirname(save_file_path))

                with open(save_file_path, 'wb') as file:
                    file.write(response.content)

            if re.match('image\/', response.headers['content-type']):
                save_file_name = re.sub('^\/', '', urlparse(response.url).path)
                save_file_path = os.path.join(self.save_dir, save_file_name)

                if not os.path.exists(os.path.dirname(save_file_path)):
                    os.makedirs(os.path.dirname(save_file_path))

                image = Image.open(BytesIO(response.content))

                # Omit under-minimum size
                # TODO: compare with max(width, height)
                if (self.min_width > 0 or self.min_height > 0) and (image.width < self.min_width and image.height < self.min_height):
                    continue

                with open(save_file_path, 'wb') as file:
                    file.write(response.content)
            elif depth < max_depth:
                self.links = []
                self.feed(response.text)
                self.crawl(self.links, max_depth, self.xorigin_policy, depth + 1)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if (tag == 'a' or tag == 'area' or tag == 'link') and 'href' in attrs:
            href = urljoin(self.current_location, attrs['href'])
        elif tag == 'img':
            href = urljoin(self.current_location, attrs['src'])
        else:
            return

        # Filter URL by regex
        # TODO: read regex from config.json, Imprement filter(url), set_filter(regex)
        # if re.search('\.jpg', attrshref):
        #    return

        if href in self.visited:
            return

        origin = urlparse(href).netloc

        # TODO: purge as bool function xorigin_policy_valid(origin)
        if self.xorigin_policy == XORIGIN_POLICY_MODERATE:
            moderate_origin = re.search('[^\.]+\.[^\.]+$', origin)
            if moderate_origin == None or moderate_origin.group(0) != self.current_moderate_origin:
                return
        elif self.xorigin_policy == XORIGIN_POLICY_RESTRICT:
            if origin == self.current_origin:
                return
        else:
            return

        self.links.append(href)

crawler = Crawler()
crawler.set_min_width_height(MIN_WIDTH, MIN_HEIGHT)
crawler.crawl(SITE_URLS, MAX_DEPTH, XORIGIN_POLICY)
