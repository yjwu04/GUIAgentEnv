from baseaction import BaseAction, execute_adb


class TapAction(BaseAction):
    name = "tap"
    description = """tap(element: int)
        This function is used to tap an UI element shown on the smartphone screen.
        "element" is a numeric tag assigned to an UI element shown on the smartphone screen.
        A simple use case can be tap(5), which taps the UI element labeled with the number 5.
    """

    def execute(self, rows, res, cols, elem_list):
        area = int(res[1])
        tl, br = elem_list[area - 1].bbox
        x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        cmd = f"adb -s {self.device} shell input tap {x} {y}"
        return execute_adb(cmd)


class TextAction(BaseAction):
    name = "text"
    description = """text(text_input: str)
        This function is used to insert text input in an input field/box. text_input is the string you want to insert and must 
        be wrapped with double quotation marks. A simple use case can be text("Hello, world!"), which inserts the string 
        "Hello, world!" into the input area on the smartphone screen. This function is usually callable when you see a keyboard 
        showing in the lower half of the screen.
    """

    def execute(self, rows, res, cols, elem_list):
        input_str = res[1]
        input_str = input_str.replace(" ", "%s")
        input_str = input_str.replace("'", "")
        cmd = f"adb -s {self.device} shell input text {input_str}"
        return execute_adb(cmd)


class LongPressAction(BaseAction):
    name = "long_press"
    description = """long_press(element: int)
        This function is used to long press an UI element shown on the smartphone screen.
        "element" is a numeric tag assigned to an UI element shown on the smartphone screen.
        A simple use case can be long_press(5), which long presses the UI element labeled with the number 5.
    """

    def execute(self, rows, res, cols, elem_list):
        area = int(res[1])
        tl, br = elem_list[area - 1].bbox
        x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        cmd = f"adb -s {self.device} shell input swipe {x} {y} {x} {y} 1000"
        return execute_adb(cmd)
    

class SwipeAction(BaseAction):
    name = "swipe"
    description = """swipe(element: int, direction: str, dist: str)
        This function is used to swipe an UI element shown on the smartphone screen, usually a scroll view or a slide bar.
        "element" is a numeric tag assigned to an UI element shown on the smartphone screen. "direction" is a string that 
        represents one of the four directions: up, down, left, right. "direction" must be wrapped with double quotation 
        marks. "dist" determines the distance of the swipe and can be one of the three options: short, medium, long. You should 
        choose the appropriate distance option according to your need.
        A simple use case can be swipe(21, "up", "medium"), which swipes up the UI element labeled with the number 21 for a 
        medium distance.
    """

    def execute(self, rows, res, cols, elem_list):
        area, direction, dist = res[1].split(",")
        area = int(area)
        direction = direction.strip()[1:-1]
        dist = dist.strip()[1:-1]
        tl, br = elem_list[area - 1].bbox
        x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2

        unit_dist = int(self.width / 10)
        if dist == "long":
            unit_dist *= 3
        elif dist == "medium":
            unit_dist *= 2
        if direction == "up":
            offset = 0, -2 * unit_dist
        elif direction == "down":
            offset = 0, 2 * unit_dist
        elif direction == "left":
            offset = -1 * unit_dist, 0
        elif direction == "right":
            offset = unit_dist, 0
        else:
            return "ERROR"
        duration =  400
        cmd = f"adb -s {self.device} shell input swipe {x} {y} {x + offset[0]} {y + offset[1]} {duration}"
        return execute_adb(cmd)
    

class TapGridAction(BaseAction):
    name = "tap_grid"
    description = """tap_grid(area: int, subarea: str)
        This function is used to tap a grid area shown on the smartphone screen. "area" is the integer label assigned to a grid 
        area shown on the smartphone screen. "subarea" is a string representing the exact location to tap within the grid area. 
        It can take one of the nine values: center, top-left, top, top-right, left, right, bottom-left, bottom, and 
        bottom-right.
        A simple use case can be tap(5, "center"), which taps the exact center of the grid area labeled with the number 5.
    """

    def area_to_xy(self, area, subarea, cols, rows):
        area -= 1
        row, col = area // cols, area % cols
        x_0, y_0 = col * (self.width // cols), row * (self.height // rows)
        if subarea == "top-left":
            x, y = x_0 + (self.width // cols) // 4, y_0 + (self.height // rows) // 4
        elif subarea == "top":
            x, y = x_0 + (self.width // cols) // 2, y_0 + (self.height // rows) // 4
        elif subarea == "top-right":
            x, y = x_0 + (self.width // cols) * 3 // 4, y_0 + (self.height // rows) // 4
        elif subarea == "left":
            x, y = x_0 + (self.width // cols) // 4, y_0 + (self.height // rows) // 2
        elif subarea == "right":
            x, y = x_0 + (self.width // cols) * 3 // 4, y_0 + (self.height // rows) // 2
        elif subarea == "bottom-left":
            x, y = x_0 + (self.width // cols) // 4, y_0 + (self.height // rows) * 3 // 4
        elif subarea == "bottom":
            x, y = x_0 + (self.width // cols) // 2, y_0 + (self.height // rows) * 3 // 4
        elif subarea == "bottom-right":
            x, y = x_0 + (self.width // cols) * 3 // 4, y_0 + (self.height // rows) * 3 // 4
        else:
            x, y = x_0 + (self.width // cols) // 2, y_0 + (self.height // rows) // 2
        return x, y


    def execute(self, rows, res, cols, elem_list):
        params = res[1].split(",")
        area = int(params[0].strip())
        subarea = params[1].strip()[1:-1]
        x, y = self.area_to_xy(area, subarea, cols, rows)
        cmd = f"adb -s {self.device} shell input tap {x} {y}"
        return execute_adb(cmd)
    

class LongPressGridAction(BaseAction):
    name = "long_press_grid"
    description = """long_press_grid(area: int, subarea: str)
        This function is used to long press a grid area shown on the smartphone screen. "area" is the integer label assigned to 
        a grid area shown on the smartphone screen. "subarea" is a string representing the exact location to long press within 
        the grid area. It can take one of the nine values: center, top-left, top, top-right, left, right, bottom-left, bottom, 
        and bottom-right.
        A simple use case can be long_press_grid(7, "top-left"), which long presses the top left part of the grid area labeled with 
        the number 7.
    """

    def area_to_xy(self, area, subarea, cols, rows):
        area -= 1
        row, col = area // cols, area % cols
        x_0, y_0 = col * (self.width // cols), row * (self.height // rows)
        if subarea == "top-left":
            x, y = x_0 + (self.width // cols) // 4, y_0 + (self.height // rows) // 4
        elif subarea == "top":
            x, y = x_0 + (self.width // cols) // 2, y_0 + (self.height // rows) // 4
        elif subarea == "top-right":
            x, y = x_0 + (self.width // cols) * 3 // 4, y_0 + (self.height // rows) // 4
        elif subarea == "left":
            x, y = x_0 + (self.width // cols) // 4, y_0 + (self.height // rows) // 2
        elif subarea == "right":
            x, y = x_0 + (self.width // cols) * 3 // 4, y_0 + (self.height // rows) // 2
        elif subarea == "bottom-left":
            x, y = x_0 + (self.width // cols) // 4, y_0 + (self.height // rows) * 3 // 4
        elif subarea == "bottom":
            x, y = x_0 + (self.width // cols) // 2, y_0 + (self.height // rows) * 3 // 4
        elif subarea == "bottom-right":
            x, y = x_0 + (self.width // cols) * 3 // 4, y_0 + (self.height // rows) * 3 // 4
        else:
            x, y = x_0 + (self.width // cols) // 2, y_0 + (self.height // rows) // 2
        return x, y


    def execute(self, rows, res, cols, elem_list):
        params = res[1].split(",")
        area = int(params[0].strip())
        subarea = params[1].strip()[1:-1]
        x, y = self.area_to_xy(area, subarea, cols, rows)
        cmd = f"adb -s {self.device} shell input swipe {x} {y} {x} {y} 1000"
        return execute_adb(cmd)
    

class SwipeGridAction(BaseAction):
    name = "swipe_grid"
    description = """swipe_grid(start_area: int, start_subarea: str, end_area: int, end_subarea: str)
        This function is used to perform a swipe action on the smartphone screen, especially when you want to interact with a 
        scroll view or a slide bar. "start_area" is the integer label assigned to the grid area which marks the starting 
        location of the swipe. "start_subarea" is a string representing the exact location to begin the swipe within the grid 
        area. "end_area" is the integer label assigned to the grid area which marks the ending location of the swipe. 
        "end_subarea" is a string representing the exact location to end the swipe within the grid area.
        The two subarea parameters can take one of the nine values: center, top-left, top, top-right, left, right, bottom-left, 
        bottom, and bottom-right.
        A simple use case can be swipe_grid(21, "center", 25, "right"), which performs a swipe starting from the center of grid area 
        21 to the right part of grid area 25.
    """

    def area_to_xy(self, area, subarea, cols, rows):
        area -= 1
        row, col = area // cols, area % cols
        x_0, y_0 = col * (self.width // cols), row * (self.height // rows)
        if subarea == "top-left":
            x, y = x_0 + (self.width // cols) // 4, y_0 + (self.height // rows) // 4
        elif subarea == "top":
            x, y = x_0 + (self.width // cols) // 2, y_0 + (self.height // rows) // 4
        elif subarea == "top-right":
            x, y = x_0 + (self.width // cols) * 3 // 4, y_0 + (self.height // rows) // 4
        elif subarea == "left":
            x, y = x_0 + (self.width // cols) // 4, y_0 + (self.height // rows) // 2
        elif subarea == "right":
            x, y = x_0 + (self.width // cols) * 3 // 4, y_0 + (self.height // rows) // 2
        elif subarea == "bottom-left":
            x, y = x_0 + (self.width // cols) // 4, y_0 + (self.height // rows) * 3 // 4
        elif subarea == "bottom":
            x, y = x_0 + (self.width // cols) // 2, y_0 + (self.height // rows) * 3 // 4
        elif subarea == "bottom-right":
            x, y = x_0 + (self.width // cols) * 3 // 4, y_0 + (self.height // rows) * 3 // 4
        else:
            x, y = x_0 + (self.width // cols) // 2, y_0 + (self.height // rows) // 2
        return x, y


    def execute(self, rows, res, cols, elem_list):
        params = res[1].split(",")
        start_area = int(params[0].strip())
        start_subarea = params[1].strip()[1:-1]
        end_area = int(params[2].strip())
        end_subarea = params[3].strip()[1:-1]
        start_x, start_y = self.area_to_xy(start_area, start_subarea)
        end_x, end_y = self.area_to_xy(end_area, end_subarea)
        cmd = f"adb -s {self.device} shell input swipe {start_x} {start_y} {end_x} {end_y} 400"
        return execute_adb(cmd)

