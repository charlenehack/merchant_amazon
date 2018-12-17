# -*- coding: utf-8 -*-
from scrapy import Spider, Request, FormRequest
from pyquery import PyQuery as pq
import re
from Amazon.items import AmazonItem

class AmazonSpider(Spider):
    name = 'amazon'
    allowed_domains = ['amazon.com', 'merchantwords.com']
  #  start_urls = ['http://amazon.com/']
    merchant_login_url = 'https://www.merchantwords.com/login'
    merchant_search_url = 'https://www.merchantwords.com/search/us/{keyword}/sort-highest'
    amazon_search_url = 'https://www.amazon.com/s/ref=sr_qz_back?sf=qz%2Crba&rh=i%3Aaps%2Ck%3A&keywords={keyword}&unfiltered=1&ie=UTF8&qid'
    has_word = set()

    def __init__(self, moci_user, moci_passwd, keyword, exclude_pool):
        self.moci_user = moci_user
        self.moci_passwd = moci_passwd
        self.keyword = keyword
        self.exclude_pool = exclude_pool

    @classmethod
    def from_crawler(cls, crawler):
    	'''从配置文件获取用户名、密码、关键字、排除关键字'''
    	return cls(
			moci_user = crawler.settings.get('MERCHANT_USER'),
			moci_passwd = crawler.settings.get('MERCHANT_PASSWORD'),
			keyword = crawler.settings.get('KEYWORD'),
			exclude_pool = crawler.settings.get('EXCLUDE_POOL')
			)

    def start_requests(self):
    	'''创建登录请求'''
    	yield FormRequest(
  			url = self.merchant_login_url, 
  			method = 'POST', 
  			formdata = {'email': self.moci_user, 'password': self.moci_passwd},
  			callback = self.check_login
  			)

    def check_login(self, response):
        '''检查是否登录成功'''
        if 'Email and password are both required' in response.text:
            print('登录失败，用户名或密码错误。')
	    exit()
        yield Request(self.merchant_search_url.format(keyword=self.keyword), callback=self.parse_moci)
    
    def parse_moci(self, response):
        '''获取一级分词'''
        doc = pq(response.text)
        for data in doc('tr'):
            words = doc(data).find('td span').eq(0).text()
            if words:
                word = words.split(' ')
                for i in word:
                    if i not in self.has_word and len(i)>1 and not re.compile('[0-9]+').findall(i) and i not in self.exclude_pool: #去重，去单个字符，去数字，去指定词
                        self.has_word.add(i)
                        yield Request(self.merchant_search_url.format(keyword=i), callback=self.parse_moci_second, dont_filter=True)

    def parse_moci_second(self, response):
    	'''获取二级分词'''
    	doc = pq(response.text)
    	for data in doc('tr'):
            pharse = doc(data).find('td span').text()
            volume = doc(data).find('td').eq(2).text().replace(',','').replace('< ','')

            if pharse and int(volume) >= 250000:
                #obj = MociItem(pharse=pharse, volume=volume)
                #yield obj
                yield Request(self.amazon_search_url.format(keyword=pharse), callback=self.parse_amazon, meta={'pharse': pharse, 'volume': volume})

    def parse_amazon(self, response):
        '''获取亚马逊爬取结果'''
        pharse = response.meta['pharse']
        volume = response.meta['volume']
        try:
	        doc = pq(response.text)
	        res = doc('#s-result-count').text().replace('\n','')
	        
	        if 'over' in res:
	            count = re.findall('over (.*) results', res)
	        elif 'of' not in res:
	            count = re.findall('(.*) results', res)
	        elif not res:
	            count = re.findall('of over (.*) results', doc)
	        else:
	            count = re.findall('of (.*) results', res)

	        mod = str(int(volume)/int(count[0].replace(',','')))
	        obj = AmazonItem(pharse=pharse, volume=count[0], mod=mod)
	        yield obj
        except Exception as e:
            print(pharse, '保存失败。', e)



        
