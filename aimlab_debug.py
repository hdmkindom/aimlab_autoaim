import cv2
import numpy as np
import win32gui
from mss import mss
import config
import logging
import time
from pynput import mouse

# 定义全局变量
aimlab_tb_hwnd = None

class BoxInfo:
    def __init__(self, box, distance):
        self.box = box
        self.distance = distance

# 获取窗口区域
def capture_screen(window_title, region_width, region_height):
    global aimlab_tb_hwnd, middle_left, middle_top
    if aimlab_tb_hwnd is None:
        aimlab_tb_hwnd = win32gui.FindWindow(None, window_title)
        if aimlab_tb_hwnd == 0:
            logging.warning("No window found")
            return None

    # 获取窗口区域大小
    left, top, right, bottom = win32gui.GetClientRect(aimlab_tb_hwnd)
    client_width = right - left
    client_height = bottom - top

    # 计算中间区域的坐标
    middle_left = client_width // 2 - region_width // 2
    middle_top = client_height // 2 - region_height // 2

    # 将客户区域的左上角坐标转换为屏幕坐标
    client_left, client_top = win32gui.ClientToScreen(aimlab_tb_hwnd, (middle_left, middle_top))

    # 使用 mss 截取指定区域
    with mss() as sct:
        monitor = {"left": client_left, "top": client_top, "width": region_width, "height": region_height}
        img = sct.grab(monitor)  # 截取屏幕区域
        frame = np.array(img)  # 转换为 numpy 数组
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)  # 转换为 BGR 格式
        return frame

# 创建 HSV 滑动条
def create_hsv_trackbars():
    cv2.namedWindow("Trackbars")
    cv2.createTrackbar("Lower H", "Trackbars", 85, 180, lambda x: None)
    cv2.createTrackbar("Upper H", "Trackbars", 95, 180, lambda x: None)
    cv2.createTrackbar("Lower S", "Trackbars", 210, 255, lambda x: None)
    cv2.createTrackbar("Upper S", "Trackbars", 245, 255, lambda x: None)
    cv2.createTrackbar("Lower V", "Trackbars", 80, 255, lambda x: None)
    cv2.createTrackbar("Upper V", "Trackbars", 255, 255, lambda x: None)

# 获取屏幕中心点坐标
def get_screen_center(img):
    screen_center_x = img.shape[1] // 2
    screen_center_y = img.shape[0] // 2
    return screen_center_x, screen_center_y

# 转化为 hsv 空间
def to_hsv(frame):
    # 从滑动条获取 HSV 范围
    lower_h = cv2.getTrackbarPos("Lower H", "Trackbars")
    lower_s = cv2.getTrackbarPos("Lower S", "Trackbars")
    lower_v = cv2.getTrackbarPos("Lower V", "Trackbars")
    upper_h = cv2.getTrackbarPos("Upper H", "Trackbars")
    upper_s = cv2.getTrackbarPos("Upper S", "Trackbars")
    upper_v = cv2.getTrackbarPos("Upper V", "Trackbars")

    lower_color = np.array([lower_h, lower_s, lower_v])
    upper_color = np.array([upper_h, upper_s, upper_v])

    # 转换到 HSV 空间
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # 根据颜色范围创建掩码
    mask = cv2.inRange(hsv, lower_color, upper_color)
    return mask

# 检测球
def detector_ball(mask, screen_center_x, screen_center_y):
    # 查找轮廓
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 直接在循环中计算最近的框体，避免额外的列表操作
    closest_box_info = None
    closest_distance = float('inf')

    # 常见轮廓处理
    for contour in contours:
        # 获取轮廓的边界框
        (circle_x, circle_y), radius = cv2.minEnclosingCircle(contour)
        
        # 计算圆心到屏幕中心的距离
        distance = ((circle_x - screen_center_x) ** 2 + (circle_y - screen_center_y) ** 2) ** 0.5

        # 更新最近的目标
        if distance < closest_distance:
            closest_box_info = BoxInfo((circle_x, circle_y, radius), distance)
            closest_distance = distance
    return closest_box_info

# 火控
def should_fire(img, fire_switch, screen_center_y, screen_center_x, fire_k, closest_box_info):
    
    if fire_switch == 1:
        # 检测中心点是否为白色
        center_pixel_value = img[screen_center_y, screen_center_x]
        is_center_white = center_pixel_value == 255
        
        if is_center_white:
            # 如果中心点为白色，表示可以开火
            logging.info("Fire detected at center point.")
            click_mouse_lift()
            return True
        else:
            logging.info("Center point is not white, no fire action taken.")
            return False
    
    if fire_switch == 0:
        # fire_k 是开火距离阈值
        if closest_box_info.distance < fire_k:
            logging.info("Target detected within fire range, firing.")
            click_mouse_lift()
            return True
        else:
            logging.info("Target is out of fire range, no fire action taken.")
            return False

# 调试部分
def debug_ball(frame, hsv, closest_box_info, screen_center_x, screen_center_y, delay_time):
    # 绘制最小外接圆
    cv2.circle(frame, (int(closest_box_info.box[0]), int(closest_box_info.box[1])), int(closest_box_info.box[2]), (255, 255, 255), 2)
    # 绘制圆心
    cv2.circle(frame, (int(closest_box_info.box[0]), int(closest_box_info.box[1])), 5, (0, 0, 255), -1)
    # 绘制屏幕中心点
    cv2.circle(frame, (screen_center_x, screen_center_y), 5, (0, 255, 0), -1)

    # 显示延迟
    delay_text = f"Delay: {delay_time:.2f} ms"
    cv2.putText(frame, delay_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow("Ball Detection", frame)
    cv2.imshow("Mask", hsv)

# 鼠标移动控制
def control_mouse_move(closest_box_info, screen_center_x, screen_center_y ):
    global controlling_mouse

    if closest_box_info:
        # 计算从屏幕中心到最近框体中心的向量
        target_x_frame = closest_box_info.box[0]
        target_y_frame = closest_box_info.box[1]
        vector_x = target_x_frame - screen_center_x
        vector_y = target_y_frame - screen_center_y

        # 设置一个阈值，当鼠标与目标的距离小于该阈值时，停止移动
        threshold = 2  # 设置阈值，越小越准，越慢

        if closest_box_info.distance > threshold:
            # 将鼠标移动一个较小的向量的距离
            step_controller = 1
            move_mouse_by(vector_x * step_controller, vector_y * step_controller)  # 减小步长
        else:
            # 一般不会出现
            click_mouse_lift()
            logging.info("distance, clicking mouse")
    else:
        logging.warning("No closest box")

# 鼠标移动控制
def move_mouse_by(delta_x, delta_y):
    config.driver_mouse_control.move_R(int(delta_x), int(delta_y))
    logging.info(f"Mouse moved by ({delta_x}, {delta_y})")

# 鼠标左键点击
def click_mouse_lift():
    config.driver_mouse_control.click_Left_down()
    config.driver_mouse_control.click_Left_up()

# 鼠标右键点击
def click_mouse_right(x, y, button, pressed):
    global controlling_mouse
    if button == mouse.Button.right and pressed:
        logging.info("Right mouse button pressed. Stopping detection.")
        controlling_mouse = False  # 停止检测

# 启动鼠标监听器
def start_mouse_listener():
    listener = mouse.Listener(on_click=click_mouse_right)
    listener.start()

def aimlab_debug():
    logging.info("aimlab_debug start ... ")

    global controlling_mouse
    controlling_mouse = True

    create_hsv_trackbars()

    while 1:
        # 记录开始时间
        start_time = time.perf_counter()

        frame = capture_screen(config.WINDOW_TITLE, config.roi_width, config.roi_height)
        if frame is None:
            continue

        screen_center_x, screen_center_y = get_screen_center(frame)

        mask = to_hsv(frame)
        
        # 检测球
        closest_box_info= detector_ball(mask, screen_center_x, screen_center_y)
        if closest_box_info is None:
            logging.warning("No ball detected.")
            continue  # 跳过当前循环
        
        control_mouse_move(closest_box_info, screen_center_x, screen_center_y)
        
        should_fire(mask, config.fire_switch, screen_center_y, screen_center_x, config.fire_k, closest_box_info)
        
        # 记录结束时间
        end_time = time.perf_counter()

        # 延迟
        delay_time = (end_time - start_time) * 1000  # 毫秒
        debug_ball(frame, mask, closest_box_info, screen_center_x, screen_center_y, delay_time)


        # # 右键关闭
        # start_mouse_listener()

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()





