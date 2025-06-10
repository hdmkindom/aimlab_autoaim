import ctypes
import yaml

# YAML
def read_yaml(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)  # 解析 YAML 文件
    return data

yaml_file = r"config\config.yaml"  # 替换 YAML 路径
yaml_data = read_yaml(yaml_file)

log_level = yaml_data['logging']['level'].upper()
dll_path = yaml_data['device']['path']
driver_mouse_control = ctypes.CDLL(dll_path)

WINDOW_TITLE = yaml_data['settings']['WINDOW_TITLE']
roi_width = yaml_data['settings']['roi_width']
roi_height = yaml_data['settings']['roi_height']
debug = yaml_data['settings']['debug']
control_mose = yaml_data['settings']['control_mose']
fire_switch = yaml_data['settings']['fire_switch']
fire_k = yaml_data['settings']['fire_k']