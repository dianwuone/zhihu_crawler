"""
Zhihu bigdata 

Author: smilexie1113@gmail.com

"""
import requests
import codecs 
import json
import time

from bs4 import BeautifulSoup
from enum import Enum

class DebugLevel(Enum):
    verbose = 1
    warning = 2
    error = 3
    end = 4

my_header = {
        'Connection': 'Keep-Alive',
        'Accept': 'text/html, application/xhtml+xml, */*',
        'Accept-Language': 'zh-CN,zh;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko',
        'Accept-Encoding': 'gzip,deflate,sdch',
        'Host': 'www.zhihu.com',
        'DNT': '1'
    }

topic_next_header = {
        'Connection': 'Keep-Alive',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.8',
        'Origin': 'http://www.zhihu.com',
        'Referer': 'http://www.zhihu.com/topics',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko',
        'Host': 'www.zhihu.com',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Content-Length': '129'
    }

def obj_to_dict(obj):
    """把ZhihuUser转成dict数据，用于ZhihuInspect。save_user中的json dump"""   
    tmp_dict = {}
    tmp_dict["name"] = obj.name
    tmp_dict["url"] = obj.user_url
    tmp_dict["thank_cnt"] = obj.thank_cnt
    tmp_dict["agree_cnt"] = obj.agree_cnt
    tmp_dict["is_male"] = obj.gender_is_male
    for key_str in ZhihuUser.extra_info_key:
        if key_str in obj.extra_info:
            tmp_dict[key_str] = obj.extra_info[key_str]
        else:
            tmp_dict[key_str] = ""
        
    return tmp_dict

class ZhihuInspect(object):
    
    def __init__(self):
        self.base_url = r"http://www.zhihu.com/"
        self.topic_square_url = r"http://www.zhihu.com/topics"
        self.first_url = self.topic_square_url
        self.email = r"xxxxx"
        self.password = r"xxxxx"
        self.debug_level = DebugLevel.verbose
        self.users = []
        self.visited_url = set() #set 查找元素的时间复杂度是O(1)
        pass

    def debug_print(self, level, log_str):
        if level.value >= self.debug_level.value:
            print(log_str)
        #todo: write log file.
    
    def save_file(self, path, str_content, encoding):
        with codecs.open(path, 'w', encoding)  as fp:
            fp.write(str_content)
    
    def save_user(self, user):
        with open("users_json.txt", "a") as fp:
            json_str = json.dumps(user, default = obj_to_dict, ensure_ascii = False, sort_keys = True)
            fp.write(json_str + "\r\n")
    
    def print_all_user(self):
        print("user num: " + str(len(self.users)))
        for user in self.users:
            print(user)
    
    def add_user(self, user):
        if user.get_url() in self.visited_url: #set 查找元素的时间复杂度是O(1)
            return False     
        else:
            self.visited_url.add(user.get_url())
            self.users.append(user)
            return True

    def init_xsrf(self):
        """初始化，获取xsrf"""
        response = requests.get(self.base_url, headers = my_header)
        text = response.text
        self.save_file("pre_page.htm", text, response.encoding)
        soup = BeautifulSoup(text, "lxml")
        input_tag = soup.find("input", {"name": "_xsrf"})
        xsrf = input_tag["value"]
        self.xsrf = xsrf
        
    def get_login_page(self):
        """获取登录后的界面，需要先运行init_xsrf"""
        login_url = self.base_url + r"login"
        post_dict = {
            'rememberme': 'y',
            'password': self.password,
            'email': self.email,
            '_xsrf':self.xsrf    
        }
        reponse_login = requests.post(login_url, headers = my_header, data = post_dict)
        self.save_file('login_page.htm', reponse_login.text, reponse_login.encoding)

    def traverse_topic(self):
        """遍历http://www.zhihu.com/topics话题广场页面顶端的标签，解析各话题"""
        response = requests.get(self.topic_square_url, headers = my_header)
        text = response.text
        self.save_file("topics.htm", text, response.encoding)
        soup = BeautifulSoup(text, "lxml")
        for li_tag in soup.find_all("li"):
            try:
                id = int(li_tag["data-id"])
                top_topic_name = li_tag.contents[0]["href"]
                self.get_topic_square_full(id, top_topic_name)
            except KeyError:
                #html页面中 li标签下无data-id属性，不处理 
                pass
        
    def get_topic_square_full(self, id, top_topic_name):
        """获取http://www.zhihu.com/topics话题广场每个标签之下，'更多'的部分"""
        next_time = 0
        self.debug_print(DebugLevel.verbose, "parse top topic %d. %s.\r\n" % (id, top_topic_name));
        
        #以下获取网页中"更多"的部分
        while True:
            post_dict = {
                'method': 'next',
                'params': r'{"topic_id":%d,"offset":%d,"hash_id":""}' % (id, next_time * 20), 
                '_xsrf': self.xsrf    
            }
            response = requests.post("http://www.zhihu.com/node/TopicsPlazzaListV2", headers = my_header, data = post_dict)
            if response.status_code != 200:
                break
            text = response.text
            self.save_file("topic_next_%d.html" % next_time, text, response.encoding)   
            next_topics = json.loads(text)
            if len(next_topics["msg"]) == 0:#msg长度为0时,表示已经请求不到数据,到达页面的底端
                break;
                
            #next_topics["msg"][0] 包含了新请求到的topic xml信息
            soup = BeautifulSoup(next_topics["msg"][0], "lxml")
            for a_tag in soup.find_all("a"):
                try:
                    if a_tag["href"].find("/topic/") == 0:
                        topic_url = r"http://www.zhihu.com" + a_tag["href"]
                        ZhihuTopic(topic_url)
                        time.sleep(0.5)
                except KeyError:
                    pass
            
            time.sleep(0.5)
            next_time += 1
        
    def get_user_url(self, url):
        """获一个页面中的所有用户链接"""
        user_url = set()
        html_text = self.get_page(url)  
        soup = BeautifulSoup(html_text, "lxml")
        
        for a_tag in soup.find_all("a"):
            try:
                if a_tag["href"].find("http://www.zhihu.com/people/") == 0:
                    user_url.add(a_tag["href"])
                elif a_tag["href"].find("/people/") == 0:
                    user_url.add(r"http://www.zhihu.com" + a_tag["href"])
            except KeyError:
                #html页面中 a标签下无href属性，不处理 
                pass
        return user_url
    
    def get_question_url(self, url):
        """获取一个页面中的所有quesion链接"""
        html_text = self.get_page(url)
        soup = BeautifulSoup(html_text, "lxml")
        question_url = set()
        for a_tag in soup.find_all("a"):
            try:
                if a_tag["href"].find("/question/") == 0:
                    tmp_url = a_tag["href"]
                    #把/question/31491363/answer/54700182 截取为 /question/31491363
                    url_end = tmp_url.find("/", len("/question/")) #第二个参数为查找的启始下标
                    if url_end > 0:
                        tmp_url = tmp_url[:url_end]
                    question_url.add(r"http://www.zhihu.com" + tmp_url)
            except KeyError:
                #html页面中 a标签下无href属性，不处理 
                pass
        return question_url
    
    def process_question_url(self, urls):
        for question_url in urls:
            user_urls = self.get_user_url(question_url)
            for user_url in user_urls:
                time.sleep(0.5) #延迟0.5s 避免被智乎认为请求过于频繁
                user = ZhihuUser(user_url)
                if user.is_valid():
                    if self.add_user(user):
                        self.save_user(user) 
            #return #todo: delete. 测试用，只处理第一个quesion url
            
    def get_page(self, url):
        try:
            response = requests.get(url, headers = my_header)
            text = response.text
            return text
        except Exception as e:
            self.debug_print(DebugLevel.warning, "fail to get " \
                             + url + " error info: " + str(e))
            return ""
    
    def get_and_save_page(self, url, path):
        try:
            response = requests.get(url, headers = my_header)
            self.save_file(path, response.text, response.encoding)
            return
        except Exception as e:
            self.debug_print(DebugLevel.warning, "fail to get " \
                             + url + " error info: " + str(e))
            return


class ZhihuTopic(object):
    def __init__(self, url):
        self.debug_level = DebugLevel.verbose
        self.url = url
        self.valid = self.parse_topic()
        if self.valid:
            self.debug_print(DebugLevel.verbose, "parse " + url + ". topic " + self.name)
        pass

    def debug_print(self, level, log_str):
        if level.value >= self.debug_level.value:
            print(log_str)
        #todo: write log file.

    def parse_topic(self):
        try:
            response = requests.get(self.url, headers = my_header)
            soup = BeautifulSoup(response.text, "lxml")
            self.soup = soup
            topic_info_tag = soup.find("h1", class_="zm-editable-content")
            self.name = topic_info_tag.contents[0]
            is_ok = True
        except Exception as err:
            self.debug_print(DebugLevel.warning, "exception raised by parsing " \
                             + self.url + " error info: " + err)
            is_ok = False
        finally:
            return is_ok
                             
class ZhihuUser(object):
    extra_info_key = ("education item", "education-extra item", "employment item", \
                      "location item", "position item");
        
    def __init__(self, user_url):
        self.debug_level = DebugLevel.verbose
        self.user_url = user_url
        self.valid = self.parse_user_page()
        if self.valid:
            self.extra_info = {}
            self.parse_extra_info()
    
    def is_valid(self):
        return self.valid
    
    def get_url(self):
        return self.user_url
    
    def debug_print(self, level, log_str):
        if level.value >= self.debug_level.value:
            print(log_str)
    
    def save_file(self, path, str_content, encoding):
        with codecs.open(path, 'w', encoding)  as fp:
            fp.write(str_content)
            
    def parse_user_page(self):
        self.debug_print(DebugLevel.verbose, "parse " + self.user_url)
        try:
            response = requests.get(self.user_url, headers = my_header)
            #self.save_file("user_page.htm", response.text, response.encoding)
            self.first_user_page_is_save = True
            soup = BeautifulSoup(response.text, "lxml")        
            self.soup = soup
            #class_即是查找class，因为class是保留字，bs框架做了转化
            name_tag = soup.find("span", class_="name")
            name = name_tag.contents[0]
            agree_tag = soup.find("span", class_="zm-profile-header-user-agree") 
            agree_cnt = agree_tag.contents[1].contents[0]
            thank_tag = soup.find("span", class_="zm-profile-header-user-thanks") 
            thank_cnt = thank_tag.contents[1].contents[0]
            gender_tag = soup.find("span", class_="item gender")
            #gender_tag.cont...nts[0]["class"]是一个list，list的每一个元素是字符串
            gender_str = gender_tag.contents[0]["class"][1]
            if gender_str.find("female") > 0:
                self.gender_is_male = False
            else:
                self.gender_is_male = True
            self.name = name
            self.thank_cnt = int(thank_cnt)
            self.agree_cnt = int(agree_cnt)
            is_ok = True
        except AttributeError:
            self.debug_print(DebugLevel.warning, "fail to parse " + self.user_url)
            is_ok = False
        except TimeoutError:
            self.debug_print(DebugLevel.warning, "get " + self.user_url + " timeout.")
            is_ok = False
        except ConnectionError: 
            self.debug_print(DebugLevel.warning, "connect " + self.user_url + " timeout.")
            is_ok = False
        except Exception as e:
            self.debug_print(DebugLevel.warning, "some other exception raised by parsing " \
                             + self.user_url + "error info: " + str(e))
            is_ok = False
        finally:
            return is_ok
    
    def parse_extra_info(self):
        #知乎上的格式类似以下形式：<span class="position item" title="流程设计">
        for key_str in self.extra_info_key:
            tag = self.soup.find("span", class_=key_str)
            if tag is not None:
                self.extra_info[key_str] = tag["title"]
        
        
    def __str__(self):
        #print类的实例打印的字符串
        out_str = "User " + self.name + " agree: " + str(self.agree_cnt) + ", " \
            "thank: " + str(self.thank_cnt) 
        if self.gender_is_male:
            out_str += " male "
        else:
            out_str += " female "
        for key_str in self.extra_info_key:
            if key_str in self.extra_info:
                out_str += " " + key_str + ": " + self.extra_info[key_str]

        return out_str

def main():
    z = ZhihuInspect()
    z.init_xsrf()
    z.traverse_topic()

    print("ok\n")

if __name__ == "__main__":    
    main()
    
