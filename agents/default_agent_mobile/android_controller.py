import os
import time
import importlib
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

def execute_adb(adb_command):
    result = subprocess.run(adb_command, shell = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True)
    if result.returncode == 0:
        return result.stdout.strip()
    raise Exception(f"Command execution failed: {adb_command}")


def list_all_devices():
    device_list = []
    try:
        result = execute_adb("adb devices")
        devices = result.split("\n")[1:]
        for d in devices:
            device_list.append(d.split()[0])
    except Exception as e:
        raise e
    return device_list


class AndroidElement:
    def __init__(self, uid, bbox, attrib):
        self.uid = uid
        self.bbox = bbox
        self.attrib = attrib


class AndroidController:

    def __init__(self, log_dir, min_dist = 30):
        try:
            devices = list_all_devices()
            self.device = devices[0]
        except Exception as e:
            raise e
        
        self.log_dir = Path(log_dir)
        self.min_dist = min_dist
        self.screenshot_dir = self.log_dir / "screenshot"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.xml_dir = self.log_dir / "xml"
        self.xml_dir.mkdir(parents=True, exist_ok=True)

        self.width, self.height = self.get_device_size()
        

    def get_device_size(self):
        adb_command = f"adb -s {self.device} shell wm size"
        try:
            result = execute_adb(adb_command)
            size_str = result.split(": ")[1].strip()
            return map(int, size_str.split("x"))
        except:
            return 0, 0


    def get_screenshot(self, prefix):
        local_path = self.screenshot_dir / f"{prefix}.png"
        adb_temp_path = f"/sdcard/{prefix}.png"
        
        try:
            cap_command = f"adb -s {self.device} shell screencap -p {adb_temp_path}"
            result = execute_adb(cap_command)
            
            pull_command = f"adb -s {self.device} pull {adb_temp_path} {local_path}"
            result = execute_adb(pull_command)
        except Exception as e:
            raise e

        return local_path


    def get_xml(self, prefix):
        local_path = self.xml_dir / f"{prefix}.xml"
        adb_temp_path = f"/sdcard/{prefix}.xml"

        try:
            dump_command = f"adb -s {self.device} shell uiautomator dump {adb_temp_path}"
            result = execute_adb(dump_command)
            
            pull_command = f"adb -s {self.device} pull {adb_temp_path} {local_path}"
            result = execute_adb(pull_command)
        except Exception as e:
            raise e
        
        return local_path


    def get_id_from_element(self, elem):
        bounds = elem.attrib["bounds"][1:-1].split("][")
        x1, y1 = map(int, bounds[0].split(","))
        x2, y2 = map(int, bounds[1].split(","))
        elem_w, elem_h = x2 - x1, y2 - y1
        if "resource-id" in elem.attrib and elem.attrib["resource-id"]:
            elem_id = elem.attrib["resource-id"].replace(":", ".").replace("/", "_")
        else:
            elem_id = f"{elem.attrib['class']}_{elem_w}_{elem_h}"
        if "content-desc" in elem.attrib and elem.attrib["content-desc"] and len(elem.attrib["content-desc"]) < 20:
            content_desc = elem.attrib['content-desc'].replace("/", "_").replace(" ", "").replace(":", "_")
            elem_id += f"_{content_desc}"
        return elem_id


    def traverse_xml_tree(self, xml_path, elem_list, attrib, add_index = False):
        path = []
        for event, elem in ET.iterparse(xml_path, ['start', 'end']):
            if event == 'start':
                path.append(elem)
                if attrib in elem.attrib and elem.attrib[attrib] == "true":
                    parent_prefix = ""
                    if len(path) > 1:
                        parent_prefix = self.get_id_from_element(path[-2])
                    bounds = elem.attrib["bounds"][1:-1].split("][")
                    x1, y1 = map(int, bounds[0].split(","))
                    x2, y2 = map(int, bounds[1].split(","))
                    center = (x1 + x2) // 2, (y1 + y2) // 2
                    elem_id = self.get_id_from_element(elem)
                    if parent_prefix:
                        elem_id = parent_prefix + "_" + elem_id
                    if add_index:
                        elem_id += f"_{elem.attrib['index']}"
                    close = False
                    for e in elem_list:
                        bbox = e.bbox
                        center_ = (bbox[0][0] + bbox[1][0]) // 2, (bbox[0][1] + bbox[1][1]) // 2
                        dist = (abs(center[0] - center_[0]) ** 2 + abs(center[1] - center_[1]) ** 2) ** 0.5
                        if dist <= self.min_dist:
                            close = True
                            break
                    if not close:
                        elem_list.append(AndroidElement(elem_id, ((x1, y1), (x2, y2)), attrib))

            if event == 'end':
                path.pop()

    def get_element_list(self, xml_path):
        clickable_list = []
        focusable_list = []
        self.traverse_xml_tree(xml_path, clickable_list, "clickable", True)
        self.traverse_xml_tree(xml_path, focusable_list, "focusable", True)
        elem_list = clickable_list.copy()
        for elem in focusable_list:
            bbox = elem.bbox
            center = (bbox[0][0] + bbox[1][0]) // 2, (bbox[0][1] + bbox[1][1]) // 2
            close = False
            for e in clickable_list:
                bbox = e.bbox
                center_ = (bbox[0][0] + bbox[1][0]) // 2, (bbox[0][1] + bbox[1][1]) // 2
                dist = (abs(center[0] - center_[0]) ** 2 + abs(center[1] - center_[1]) ** 2) ** 0.5
                if dist <= self.min_dist:
                    close = True
                    break
            if not close:
                elem_list.append(elem)

        return elem_list


    def load_actions_from_file(self, path):
        module_name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(dir(module))
        actions = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            try:
                if issubclass(attr, module.BaseAction) and attr is not module.BaseAction:
                    actions.append(attr)
            except TypeError:
                continue
        return actions


    def execute_action(self, response, rows, cols, elem_list, action_list):
        action_name = response[0]
        action = {
            "name": action_name,
            "params": None
        }     

        if action_name == "FINISH":
            return action, "Success", None
        if action_name == "ERROR":
            return action, "Error", None
        if action_name == "grid":
            return action, "Success", None
        
        action_classes = self.load_actions_from_file(action_list)
        
        action_cls = next((cls for cls in action_classes if cls.name == action_name), None)
        if not action_cls:
            print(f"ERROR: action {action_name} not found in action_list", "red")        
            return {"name": action_name, "params": None}, "Error"
        
        last_action = response[-1]
        response = response[:-1]

        action_instance = action_cls(self.device)
        try:
            action_instance.execute(rows, response, cols, elem_list)
            action_result = "Success"
        except:
            action_result = "Error"
        
        time.sleep(10)
        return  action, action_result, last_action
    