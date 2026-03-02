import platform
import time
import json
import re
import os
import sys
import argparse
import shutil
import logging
import urllib.request
import tarfile
from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
current_dir = os.path.dirname(os.path.abspath(__file__))
webvoyager_main_path = os.path.join(current_dir, "WebVoyager_main")
agents_root_path = os.path.dirname(current_dir)
# Ensure imports work whether treating WebVoyager_main as a package or by path
for p in [webvoyager_main_path, current_dir, agents_root_path]:
    if p and p not in sys.path:
        sys.path.insert(0, p)


from WebVoyager_main.prompts import SYSTEM_PROMPT, SYSTEM_PROMPT_TEXT_ONLY
from WebVoyager_main.utils import get_web_element_rect, encode_image, extract_information, print_message,\
    get_webarena_accessibility_tree, get_pdf_retrieval_ans_from_assistant, clip_message_and_obs, clip_message_and_obs_text_only

from agent_base import AgentAdapter, AgentStepResult


class WebVoyagerAgent(AgentAdapter):
    def driver_config(self, args):
        options = webdriver.ChromeOptions()
        if args["force_device_scale"]:
            options.add_argument("--force-device-scale-factor=1") 
        if args["headless"]: 
            options.add_argument("--headless")
            options.add_experimental_option("prefs", { 
                "download.default_directory": args["download_dir"],
                "plugins.always_open_pdf_externally": True 
            }) 
        return options


    def setup_logger(self, folder_path):
        log_file_path = os.path.join(folder_path, 'agent.log')

        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()

        handler = logging.FileHandler(log_file_path)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


    def init(self, model, key, max_steps = 10, window_width = 1024, window_height = 768, text_only = False, fix_box_color = False, save_accessibility_tree = False, force_device_scale = False, headless = True, downloads_dir = "downloads", task_dir = "", max_attached_imgs = 1) -> None:
        """Reset agent state for a new test case."""
        def to_bool(val):
            if isinstance(val, bool):
                return val
            return str(val).strip().lower() in ("1", "true", "yes", "y", "on")
        self.max_steps = max_steps
        self.model = model
        self.download_dir = downloads_dir
        self.task_dir = task_dir
        self.text_only = to_bool(text_only)
        self.max_attached_imgs = max_attached_imgs
        # for web browser
        self.headless = to_bool(headless)
        self.save_accessibility_tree = to_bool(save_accessibility_tree)
        self.force_device_scale = to_bool(force_device_scale)
        if save_accessibility_tree:
            self.force_device_scale = True
        self.window_width = window_width
        self.window_height = window_height
        self.fix_box_color = to_bool(fix_box_color)

        self.client = OpenAI(api_key = key)
        self.options = self.driver_config({
            "headless": headless,
            "force_device_scale": force_device_scale,
            "download_dir": downloads_dir,
        })
        arch = platform.machine().lower()
        chrome_bin = os.getenv("CHROME_BIN", "").strip()
        chrome_driver = os.getenv("CHROMEDRIVER", "").strip()

        # Harden defaults for containerized Chrome
        for arg in ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--remote-debugging-port=9222"]:
            if arg not in self.options.arguments:
                self.options.add_argument(arg)

        self.driver = None
        # Prefer Chrome only if explicitly provided; otherwise use Firefox on arm (Chrome not available).
        if chrome_bin:
            self.options.binary_location = chrome_bin
        if chrome_driver:
            try:
                logging.info("Starting Chrome with CHROMEDRIVER=%s", chrome_driver)
                self.driver = webdriver.Chrome(service=Service(chrome_driver), options=self.options)
            except Exception as e:
                logging.error("Chrome start failed (explicit driver): %s", e)

        if self.driver is None and arch not in ("arm64", "aarch64", "armv7l", "armv8", "arm"):
            try:
                logging.info("Starting Chrome via Selenium Manager")
                self.driver = webdriver.Chrome(options=self.options)
            except Exception as e:
                logging.warning("Chrome via Selenium Manager failed: %s", e)

        if self.driver is None:
            self.driver = self._start_firefox()
            if self.driver is None:
                raise RuntimeError("Failed to start Firefox (no driver).")

        self.driver.set_window_size(window_width, window_height)  # larger height may contain more web information
        self.download_files = []  # sorted(os.listdir(args.download_dir))
        self.fail_obs = None  # When error execute the action
        self.pdf_obs = ""  # When download PDF file
        self.warn_obs = ""  # Type warning
        self.messages = []
        self.init_msg = ""
        self.web_eles = None
        self.web_eles_text = None
        self.obs_info = None
        self.task = ""

        os.makedirs(self.task_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)
        self.setup_logger(self.task_dir)


    def format_msg(self, it, init_msg, pdf_obs, warn_obs, web_img_b64, web_text):
        if it == 1:
            init_msg += f"I've provided the tag name of each element and the text it contains (if text exists). Note that <textarea> or <input> may be textbox, but not exactly. Please focus more on the screenshot and then refer to the textual information.\n{web_text}"
            init_msg_format = {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': init_msg},
                ]
            }
            init_msg_format['content'].append({"type": "image_url",
                                            "image_url": {"url": f"data:image/png;base64,{web_img_b64}"}})
            return init_msg_format
        else:
            if not pdf_obs:
                curr_msg = {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': f"Observation:{warn_obs} please analyze the attached screenshot and give the Thought and Action. I've provided the tag name of each element and the text it contains (if text exists). Note that <textarea> or <input> may be textbox, but not exactly. Please focus more on the screenshot and then refer to the textual information.\n{web_text}"},
                        {
                            'type': 'image_url',
                            'image_url': {"url": f"data:image/png;base64,{web_img_b64}"}
                        }
                    ]
                }
            else:
                curr_msg = {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': f"Observation: {pdf_obs} Please analyze the response given by Assistant, then consider whether to continue iterating or not. The screenshot of the current page is also attached, give the Thought and Action. I've provided the tag name of each element and the text it contains (if text exists). Note that <textarea> or <input> may be textbox, but not exactly. Please focus more on the screenshot and then refer to the textual information.\n{web_text}"},
                        {
                            'type': 'image_url',
                            'image_url': {"url": f"data:image/png;base64,{web_img_b64}"}
                        }
                    ]
                }
            return curr_msg


    def format_msg_text_only(self, it, init_msg, pdf_obs, warn_obs, ac_tree):
        if it == 1:
            init_msg_format = {
                'role': 'user',
                'content': init_msg + '\n' + ac_tree
            }
            return init_msg_format
        else:
            if not pdf_obs:
                curr_msg = {
                    'role': 'user',
                    'content': f"Observation:{warn_obs} please analyze the accessibility tree and give the Thought and Action.\n{ac_tree}"
                }
            else:
                curr_msg = {
                    'role': 'user',
                    'content': f"Observation: {pdf_obs} Please analyze the response given by Assistant, then consider whether to continue iterating or not. The accessibility tree of the current page is also given, give the Thought and Action.\n{ac_tree}"
                }
            return curr_msg


    def call_gpt4v_api(self, openai_client, messages):
        retry_times = 0
        while True:
            try:
                if not self.text_only:
                    logging.info('Calling gpt4v API...')
                    openai_response = openai_client.chat.completions.create(
                        model=self.model, messages=messages, max_tokens=1000
                    )
                else:
                    logging.info('Calling gpt4 API...')
                    openai_response = openai_client.chat.completions.create(
                        model=self.model, messages=messages, max_tokens=1000, timeout=30
                    )

                prompt_tokens = openai_response.usage.prompt_tokens
                completion_tokens = openai_response.usage.completion_tokens

                logging.info(f'Prompt Tokens: {prompt_tokens}; Completion Tokens: {completion_tokens}')

                gpt_call_error = False
                return prompt_tokens, completion_tokens, gpt_call_error, openai_response

            except Exception as e:
                print(e)
                logging.info(f'Error occurred, retrying. Error type: {type(e).__name__}')

                if type(e).__name__ == 'RateLimitError':
                    time.sleep(10)

                elif type(e).__name__ == 'APIError':
                    time.sleep(15)

                elif type(e).__name__ == 'InvalidRequestError':
                    gpt_call_error = True
                    return None, None, gpt_call_error, None

                else:
                    gpt_call_error = True
                    return None, None, gpt_call_error, None

            retry_times += 1
            if retry_times == 10:
                logging.info('Retrying too many times')
                return None, None, True, None


    def step(self, it) -> AgentStepResult:
        """Given input (prompt / UI state / etc.), produce one step result."""
        rects = None
        observation_before = None
        observation_after = None
        if not self.fail_obs:
            try:
                if not self.text_only:
                    rects, self.web_eles, self.web_eles_text = get_web_element_rect(self.driver, fix_color=self.fix_box_color)
                else:
                    accessibility_tree_path = os.path.join(self.task_dir, 'accessibility_tree{}'.format(it))
                    ac_tree, self.obs_info = get_webarena_accessibility_tree(self.driver, accessibility_tree_path)

            except Exception as e:
                raise e

            img_path = os.path.join(self.task_dir, 'screenshot{}_before.png'.format(it))
            self.driver.save_screenshot(img_path)
            observation_before = img_path

            # accessibility tree
            if (not self.text_only) and self.save_accessibility_tree:
                accessibility_tree_path = os.path.join(self.task_dir, 'accessibility_tree{}'.format(it))
                get_webarena_accessibility_tree(self.driver, accessibility_tree_path)

            # encode image
            b64_img = encode_image(img_path)

            # format msg
            if not self.text_only:
                curr_msg = self.format_msg(it, self.init_msg, self.pdf_obs, self.warn_obs, b64_img, self.web_eles_text)
            else:
                curr_msg = self.format_msg_text_only(it, self.init_msg, self.pdf_obs, self.warn_obs, ac_tree)
            self.messages.append(curr_msg)
        else:
            curr_msg = {
                'role': 'user',
                'content': self.fail_obs
            }
            self.messages.append(curr_msg)

    # Clip messages, too many attached images may cause confusion
        if not self.text_only:
            self.messages = clip_message_and_obs(self.messages, self.max_attached_imgs)
        else:
            self.messages = clip_message_and_obs_text_only(self.messages, self.max_attached_imgs)

        # Call GPT-4v API
        prompt_tokens, completion_tokens, gpt_call_error, openai_response = self.call_gpt4v_api(self.client, self.messages)
        print(openai_response)
        if gpt_call_error:
            raise Exception(gpt_call_error)
        gpt_4v_res = openai_response.choices[0].message.content
        self.messages.append({'role': 'assistant', 'content': gpt_4v_res})


        # remove the rects on the website
        if (not self.text_only) and rects:
            logging.info(f"Num of interactive elements: {len(rects)}")
            for rect_ele in rects:
                self.driver.execute_script("arguments[0].remove()", rect_ele)
            rects = []
            # driver_task.save_screenshot(os.path.join(task_dir, 'screenshot{}_no_box.png'.format(it)))

        filtered_messages = [
            {**msg, 'content': [c for c in msg['content'] if c['type'] != 'image_url']}
            for msg in self.messages[:-1]
        ]

        # extract action info
        try:
            assert 'Thought:' in gpt_4v_res and 'Action:' in gpt_4v_res
        except AssertionError as e:
            logging.error(e)
            self.fail_obs = "Format ERROR: Both 'Thought' and 'Action' should be included in your reply."
            return AgentStepResult(
                input = filtered_messages,
                observation_before = {"image": observation_before},
                action = None,
                action_result={"action_result": "ERROR"},
                observation_after = None,
                output = self.fail_obs
            )

        pattern = r'Thought:|Action:|Observation:'
        # bot_thought = re.split(pattern, gpt_4v_res)[1].strip()
        chosen_action = re.split(pattern, gpt_4v_res)[2].strip()
        # print(chosen_action)
        action_key, info = extract_information(chosen_action)

        self.fail_obs = None
        self.pdf_obs = ""
        self.warn_obs = ""

        self.exec_action(action_key, info)
        img_path = os.path.join(self.task_dir, 'screenshot{}_after.png'.format(it))
        self.driver.save_screenshot(img_path)
        observation_after = img_path

        return AgentStepResult(
            input = filtered_messages,
            observation_before = {"image": observation_before},
            action = {   
                "action_key" : action_key,
                "info": info
            },
            action_result = {"action_result": "SUCCESS" if self.fail_obs is None else self.fail_obs},
            observation_after = {"image": observation_after},
            output = gpt_4v_res
        )


    def exec_action_type(self, info, web_ele, driver_task):
        warn_obs = ""
        type_content = info['content']

        ele_tag_name = web_ele.tag_name.lower()
        ele_type = web_ele.get_attribute("type")
        # outer_html = web_ele.get_attribute("outerHTML")
        if (ele_tag_name != 'input' and ele_tag_name != 'textarea') or (ele_tag_name == 'input' and ele_type not in ['text', 'search', 'password', 'email', 'tel']):
            warn_obs = f"note: The web element you're trying to type may not be a textbox, and its tag name is <{web_ele.tag_name}>, type is {ele_type}."
        try:
            # Not always work to delete
            web_ele.clear()
            # Another way to delete
            if platform.system() == 'Darwin':
                web_ele.send_keys(Keys.COMMAND + "a")
            else:
                web_ele.send_keys(Keys.CONTROL + "a")
            web_ele.send_keys(" ")
            web_ele.send_keys(Keys.BACKSPACE)
        except:
            pass

        actions = ActionChains(driver_task)
        actions.click(web_ele).perform()
        actions.pause(1)

        try:
            driver_task.execute_script("""window.onkeydown = function(e) {if(e.keyCode == 32 && e.target.type != 'text' && e.target.type != 'textarea' && e.target.type != 'search') {e.preventDefault();}};""")
        except:
            pass

        actions.send_keys(type_content)
        actions.pause(2)

        actions.send_keys(Keys.ENTER)
        actions.perform()
        time.sleep(10)
        return warn_obs


    def exec_action_scroll(self, info, web_eles, driver_task, obs_info):
        scroll_ele_number = info['number']
        scroll_content = info['content']
        if scroll_ele_number == "WINDOW":
            if scroll_content == 'down':
                driver_task.execute_script(f"window.scrollBy(0, {self.window_height*2//3});")
            else:
                driver_task.execute_script(f"window.scrollBy(0, {-self.window_height*2//3});")
        else:
            if not self.text_only:
                scroll_ele_number = int(scroll_ele_number)
                web_ele = web_eles[scroll_ele_number]
            else:
                element_box = obs_info[scroll_ele_number]['union_bound']
                element_box_center = (element_box[0] + element_box[2] // 2, element_box[1] + element_box[3] // 2)
                web_ele = driver_task.execute_script("return document.elementFromPoint(arguments[0], arguments[1]);", element_box_center[0], element_box_center[1])
            actions = ActionChains(driver_task)
            driver_task.execute_script("arguments[0].focus();", web_ele)
            if scroll_content == 'down':
                actions.key_down(Keys.ALT).send_keys(Keys.ARROW_DOWN).key_up(Keys.ALT).perform()
            else:
                actions.key_down(Keys.ALT).send_keys(Keys.ARROW_UP).key_up(Keys.ALT).perform()
        time.sleep(3)


    def exec_action(self, action_key, info) -> str:
        try:
            window_handle_task = self.driver.current_window_handle
            self.driver.switch_to.window(window_handle_task)

            if action_key == 'click':
                if not self.text_only:
                    click_ele_number = int(info[0])
                    web_ele = self.web_eles[click_ele_number]
                else:
                    click_ele_number = info[0]
                    element_box = self.obs_info[click_ele_number]['union_bound']
                    element_box_center = (element_box[0] + element_box[2] // 2,
                                            element_box[1] + element_box[3] // 2)
                    web_ele = self.driver.execute_script("return document.elementFromPoint(arguments[0], arguments[1]);", element_box_center[0], element_box_center[1])

                ele_tag_name = web_ele.tag_name.lower()
                ele_type = web_ele.get_attribute("type")

                self.driver.execute_script("arguments[0].setAttribute('target', '_self')", web_ele)
                web_ele.click()
                time.sleep(3)

                # deal with PDF file
                current_files = sorted(os.listdir(self.download_dir))
                if current_files != download_files:
                    # wait for download finish
                    time.sleep(10)
                    current_files = sorted(os.listdir(self.download_dir))

                    current_download_file = [pdf_file for pdf_file in current_files if pdf_file not in download_files and pdf_file.endswith('.pdf')]
                    if current_download_file:
                        pdf_file = current_download_file[0]
                        pdf_obs = get_pdf_retrieval_ans_from_assistant(self.client, os.path.join(self.download_dir, pdf_file), self.task['ques'])
                        shutil.copy(os.path.join(self.download_dir, pdf_file), self.task_dir)
                        pdf_obs = "You downloaded a PDF file, I ask the Assistant API to answer the task based on the PDF file and get the following response: " + pdf_obs
                    download_files = current_files

                if ele_tag_name == 'button' and ele_type == 'submit':
                    time.sleep(10)

            elif action_key == 'wait':
                time.sleep(5)

            elif action_key == 'type':
                if not self.text_only:
                    type_ele_number = int(info['number'])
                    web_ele = self.web_eles[type_ele_number]
                else:
                    type_ele_number = info['number']
                    element_box = self.obs_info[type_ele_number]['union_bound']
                    element_box_center = (element_box[0] + element_box[2] // 2,
                                            element_box[1] + element_box[3] // 2)
                    web_ele = self.driver.execute_script("return document.elementFromPoint(arguments[0], arguments[1]);", element_box_center[0], element_box_center[1])

                self.warn_obs = self.exec_action_type(info, web_ele, self.driver)
                if 'wolfram' in self.task['web']:
                    time.sleep(5)

            elif action_key == 'scroll':
                if not self.text_only:
                    self.exec_action_scroll(info, self.web_eles, self.driver, None)
                else:
                    self.exec_action_scroll(info, None, self.driver, self.obs_info)

            elif action_key == 'goback':
                self.driver.back()
                time.sleep(2)

            elif action_key == 'google':
                self.driver.get('https://www.google.com/')
                time.sleep(2)

            elif action_key == 'answer':
                logging.info(info['content'])
                logging.info('finish!!')
            else:
                raise NotImplementedError
            self.fail_obs = None
        except Exception as e:
            logging.error('driver error info:')
            logging.error(e)
            if 'element click intercepted' not in str(e):
                self.fail_obs = "The action you have chosen cannot be exected. Please double-check if you have selected the wrong Numerical Label or Action or Action format. Then provide the revised Thought and Action."
            else:
                self.fail_obs = None
            time.sleep(2)


    def run(self, task) -> AgentStepResult:
        """High-level execution for a full task."""
        print(task)
        print(type(task))
        if isinstance(task, str):
            url_match = re.search(r'https?://[^\s\)\]\"\',]+', task)
            print(url_match)
            if url_match:
                url = url_match.group(0)
            else:
                url = "https://www.google.com"
            self.task = {
                "ques" : task,
                "web" : url
            }
        else:
            self.task = task

        self.driver.get(self.task['web'])
        try:
            self.driver.find_element(By.TAG_NAME, 'body').click()
        except:
            pass
        self.driver.execute_script("""window.onkeydown = function(e) {if(e.keyCode == 32 && e.target.type != 'text' && e.target.type != 'textarea') {e.preventDefault();}};""")
        time.sleep(5)

        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir, exist_ok=True)

        for filename in os.listdir(self.download_dir):
            file_path = os.path.join(self.download_dir, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

        self.messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        obs_prompt = "Observation: please analyze the attached screenshot and give the Thought and Action. "
        if self.text_only:
            self.messages = [{'role': 'system', 'content': SYSTEM_PROMPT_TEXT_ONLY}]
            obs_prompt = "Observation: please analyze the accessibility tree and give the Thought and Action."

        self.init_msg = f"""Now given a task: {self.task['ques']}  Please interact with https://www.example.com and get the answer. \n"""
        self.init_msg = self.init_msg.replace('https://www.example.com', self.task['web'])
        self.init_msg = self.init_msg + obs_prompt

        results = []
        for i in range(self.max_steps):
            result = self.step(i)
            results.append(result)

        self.driver.quit()
        return results


    def _start_firefox(self):
        """Fallback browser if Chrome/Chromedriver is unavailable (arm64-friendly)."""
        try:
            ff_opts = FirefoxOptions()
            if self.headless:
                ff_opts.add_argument("-headless")
            ff_bin = os.getenv("FIREFOX_BIN", "").strip()
            if ff_bin:
                ff_opts.binary_location = ff_bin
            else:
                for candidate in ("/usr/bin/firefox-esr", "/usr/bin/firefox"):
                    if os.path.exists(candidate):
                        ff_opts.binary_location = candidate
                        break
            gecko_path = os.getenv("GECKODRIVER", "").strip()
            if not gecko_path:
                gecko_path = shutil.which("geckodriver") or "/usr/local/bin/geckodriver"
            if not gecko_path or not os.path.exists(gecko_path):
                gecko_path = self._download_geckodriver()
            if not gecko_path or not os.path.exists(gecko_path):
                logging.error("Geckodriver not found; set GECKODRIVER to its path.")
                return None
            service = FirefoxService(executable_path=gecko_path)
            logging.info("Starting Firefox with geckodriver=%s", gecko_path)
            return webdriver.Firefox(service=service, options=ff_opts)
        except Exception as e:
            logging.error("Failed to start Firefox: %s", e)
            return None


    def _download_geckodriver(self):
        """Minimal fetch of geckodriver for current arch."""
        arch = platform.machine().lower()
        if arch.startswith("arm") or arch.startswith("aarch64"):
            suffix = "linux-aarch64"
        elif arch in ("x86_64", "amd64"):
            suffix = "linux64"
        else:
            logging.error("Unsupported arch for geckodriver download: %s", arch)
            return None
        version = "v0.35.0"
        url = f"https://github.com/mozilla/geckodriver/releases/download/{version}/geckodriver-{version}-{suffix}.tar.gz"
        cache_dir = os.path.join(current_dir, ".gecko-cache")
        os.makedirs(cache_dir, exist_ok=True)
        archive_path = os.path.join(cache_dir, f"geckodriver-{suffix}.tar.gz")
        try:
            logging.info("Downloading geckodriver (%s)", url)
            urllib.request.urlretrieve(url, archive_path)
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extract("geckodriver", path=cache_dir)
            gecko_path = os.path.join(cache_dir, "geckodriver")
            os.chmod(gecko_path, 0o755)
            return gecko_path
        except Exception as e:
            logging.error("Geckodriver download failed: %s", e)
            return None

if __name__ == "__main__":
    agent = WebVoyagerAgent()
    agent.init(
        model = "gpt-4o",
        key = os.getenv("OPENAI_API_KEY", "")
    )
    agent.run({
        "ques": "find a picture of cat for me.",
        "web": "https://google.com"
    })
