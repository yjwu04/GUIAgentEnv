import subprocess


def execute_adb(adb_command):
    print(f"Command executed: {adb_command}")
    result = subprocess.run(adb_command, shell = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True)
    if result.returncode == 0:
        return result.stdout.strip()
    raise Exception(f"Command execution failed: {adb_command}")


class BaseAction:
    name = ""
    description = ""

    def __init__(self, device = None, width = None, height = None):
        self.width = width
        self.height = height
        self.device = device

    def execute(self, res, rows, cols, elem_list):
        raise NotImplementedError("execute must be implemented by subclass")