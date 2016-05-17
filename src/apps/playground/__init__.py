import utime
from trezor import loop
from trezor import ui
from trezor.utils import unimport_func


def in_area(pos, area):
    x, y = pos
    ax, ay, aw, ah = area
    return ax <= x <= ax + aw and ay <= y <= ay + ah


DEFAULT_BUTTON = {
    'bg-color': ui.BLACK,
    'fg-color': ui.WHITE,
    'text-style': ui.NORMAL,
    'border-color': ui.blend(ui.BLACK, ui.WHITE, 0.1),
}
DEFAULT_BUTTON_ACTIVE = {
    'bg-color': ui.GREY,
    'fg-color': ui.BLACK,
    'text-style': ui.BOLD,
    'border-color': ui.GREY,
}

CANCEL_BUTTON = {
    'bg-color': ui.blend(ui.BLACK, ui.RED, 0.3),
    'fg-color': ui.RED,
    'text-style': ui.NORMAL,
    'border-color': ui.blend(ui.BLACK, ui.RED, 0.6),
}
CANCEL_BUTTON_ACTIVE = {
    'bg-color': ui.RED,
    'fg-color': ui.WHITE,
    'text-style': ui.BOLD,
    'border-color': ui.RED,
}

CONFIRM_BUTTON = {
    'bg-color': ui.blend(ui.BLACK, ui.GREEN, 0.3),
    'fg-color': ui.GREEN,
    'text-style': ui.NORMAL,
    'border-color': ui.blend(ui.BLACK, ui.GREEN, 0.6),
}
CONFIRM_BUTTON_ACTIVE = {
    'bg-color': ui.GREEN,
    'fg-color': ui.WHITE,
    'text-style': ui.BOLD,
    'border-color': ui.GREEN,
}


BTN_CLICKED = const(1)

BTN_STARTED = const(1)
BTN_ACTIVE = const(2)
BTN_DIRTY = const(4)


class Button():

    def __init__(self, area, text, normal_style=None, active_style=None):
        self.area = area
        self.text = text
        self.normal_style = normal_style or DEFAULT_BUTTON
        self.active_style = active_style or DEFAULT_BUTTON_ACTIVE
        self.state = BTN_DIRTY

    def render(self):
        if not self.state & BTN_DIRTY:
            return
        state = self.state & ~BTN_DIRTY
        style = self.active_style if state & BTN_ACTIVE else self.normal_style
        ax, ay, aw, ah = self.area
        tx = ax + aw // 2
        ty = ay + ah // 2 + 8
        ui.display.bar(ax, ay, aw, ah, style['border-color'])
        ui.display.bar(ax + 1, ay + 1, aw - 2, ah - 2, style['bg-color'])
        ui.display.text_center(tx, ty, self.text,
                               style['text-style'],
                               style['fg-color'],
                               style['bg-color'])
        self.state = state

    def send(self, event, pos):
        if event is loop.TOUCH_START:
            if in_area(pos, self.area):
                self.state = BTN_STARTED | BTN_DIRTY | BTN_ACTIVE
        elif event is loop.TOUCH_MOVE and self.state & BTN_STARTED:
            if in_area(pos, self.area):
                if not self.state & BTN_ACTIVE:
                    self.state = BTN_STARTED | BTN_DIRTY | BTN_ACTIVE
            else:
                if self.state & BTN_ACTIVE:
                    self.state = BTN_STARTED | BTN_DIRTY
        elif event is loop.TOUCH_END and self.state & BTN_STARTED:
            self.state = BTN_DIRTY
            if in_area(pos, self.area):
                return BTN_CLICKED


def digit_area(d):
    width = const(80)
    height = const(60)
    x = ((d - 1) % 3) * width
    y = ((d - 1) // 3) * height
    return (x, y, width, height)


PIN_CONFIRMED = const(1)
PIN_CANCELLED = const(2)


class PinDialog():

    def __init__(self, pin=''):
        self.pin = pin
        self.confirm_button = Button((0, 240 - 60, 120, 60), 'Confirm',
                                     normal_style=CONFIRM_BUTTON,
                                     active_style=CONFIRM_BUTTON_ACTIVE)
        self.cancel_button = Button((120, 240 - 60, 120, 60), 'Cancel',
                                    normal_style=CANCEL_BUTTON,
                                    active_style=CANCEL_BUTTON_ACTIVE)
        self.pin_buttons = [Button(digit_area(dig), str(dig))
                            for dig in range(1, 10)]

    def render(self):
        for btn in self.pin_buttons:
            btn.render()
        self.confirm_button.render()
        self.cancel_button.render()

    def send(self, event, pos):
        for btn in self.pin_buttons:
            if btn.send(event, pos) is BTN_CLICKED:
                self.pin += btn.text
        if self.confirm_button.send(event, pos) is BTN_CLICKED:
            return PIN_CONFIRMED
        if self.cancel_button.send(event, pos) is BTN_CLICKED:
            return PIN_CANCELLED

    def wait_for_result(self):
        while True:
            self.render()
            event, *pos = yield loop.Select(loop.TOUCH_START,
                                            loop.TOUCH_MOVE,
                                            loop.TOUCH_END)
            result = self.send(event, pos)
            if result is not None:
                return result


SWIPE_DISTANCE_THRESHOLD = const(20)  # Min pixels in the primary direction
SWIPE_VELOCITY_THRESHOLD = const(200)  # Min pixels/second
SWIPE_RATIO_THRESHOLD = const(30)  # Max ratio secondary to primary direction in %

SWIPE_UP = const(180)
SWIPE_DOWN = const(0)
SWIPE_LEFT = const(90)
SWIPE_RIGHT = const(270)


class Swipe():

    def __init__(self, area=None):
        self.area = area or (0, 0, 240, 240)
        self.start_pos = None
        self.start_time = 0
        self.end_pos = None
        self.end_time = 0

    def send(self, event, pos):

        if event is loop.TOUCH_START and in_area(pos, self.area):
            self.start_time = utime.time()
            self.start_pos = pos

        elif event is loop.TOUCH_END and self.start_pos is not None:
            self.end_time = utime.time()
            self.end_pos = pos
            td = self.end_time - self.start_time
            pdx = self.end_pos[0] - self.start_pos[0]
            pdy = self.end_pos[1] - self.start_pos[1]
            pdxa = abs(pdx)
            pdya = abs(pdy)
            if pdxa > pdya:
                # Horizontal direction
                velx = pdx / td
                velxa = abs(velx)
                ratio = int(pdya / pdxa * 100) if pdxa > 0 else 100
                print('velxa', velxa, 'pdxa', pdxa, 'ratio', ratio)
                if (velxa >= SWIPE_VELOCITY_THRESHOLD
                        and pdxa >= SWIPE_DISTANCE_THRESHOLD
                        and ratio <= SWIPE_RATIO_THRESHOLD):
                    return SWIPE_RIGHT if pdx > 0 else SWIPE_LEFT
            else:
                # Vertical direction
                vely = pdy / td
                velya = abs(vely)
                ratio = int(pdxa / pdya * 100) if pdya > 0 else 100
                print('velya', velya, 'pdya', pdya, 'ratio', ratio)
                if (velya >= SWIPE_VELOCITY_THRESHOLD
                        and pdya >= SWIPE_DISTANCE_THRESHOLD
                        and ratio <= SWIPE_RATIO_THRESHOLD):
                    return SWIPE_DOWN if pdy > 0 else SWIPE_UP
            # No swipe, reset the state
            self.start_pos = None
            self.start_time = 0
            self.end_pos = None
            self.end_time = 0

    def wait(self):
        while True:
            event, *pos = yield loop.Select(loop.TOUCH_START, loop.TOUCH_END)
            result = self.send(event, pos)
            if result is not None:
                return result


def layout_tap_to_confirm(address, amount, currency):

    # ui.display.bar(0, 0, 240, 40, ui.GREEN)
    # ui.display.bar(0, 40, 240, 200, ui.WHITE)

    # ui.display.text(10, 28, 'Sending', ui.BOLD, ui.WHITE, ui.GREEN)
    # ui.display.text(10, 80, '%f %s' % (amount, currency), ui.BOLD, ui.BLACK, ui.WHITE)
    # ui.display.text(10, 110, 'to this address:', ui.NORMAL, ui.BLACK, ui.WHITE)
    # ui.display.text(10, 140, address[:18], ui.MONO, ui.BLACK, ui.WHITE)
    # ui.display.text(10, 160, address[18:], ui.MONO, ui.BLACK, ui.WHITE)

    # f = open('apps/playground/tap_64.toig', 'rb')
    # bg = ui.WHITE
    # style = ui.NORMAL

    # def func(fg):
    #     ui.display.text(68, 212, 'TAP TO CONFIRM', style, fg, bg)
    #     f.seek(0)
    #     ui.display.icon(3, 170, f.read(), bg, fg)

    # animation = ui.animate_pulse(func, ui.BLACK, ui.GREY, speed=200000)

    # pin_dialog = PinDialog()
    # pin_result = yield from pin_dialog.wait_for_result()

    # if pin_result is PIN_CONFIRMED:
    #     print('PIN confirmed:', pin_dialog.pin)

    # elif pin_result is PIN_CANCELLED:
    #     print('PIN CANCELLED, go home')

    degrees = 0

    while True:
        ui.display.bar(0, 0, 240, 240, ui.BLACK)
        ui.display.text_center(120, 130, 'HELLO WORLD!', ui.NORMAL, ui.WHITE, ui.BLACK)
        degrees = yield from Swipe().wait()
        ui.display.orientation(degrees)


@unimport_func
def zprava():
    from uio import BytesIO

    from trezor.messages.GetAddress import GetAddress

    m = GetAddress()
    m.address_n = [1, 2, 3]
    m.show_display = True

    print(m.__dict__)
    f = BytesIO()
    m.dump(f)
    data = f.getvalue()
    f.close()
    print(data)
    # m2 = GetAddress.load(BytesIO(data))
    # print(m2.__dict__)


def dispatch():
    # Callback for HID messages
    print("Dispatch playground")


def boot():
    # Initilize app on boot time.
    # This should hookup HID message types dispatcher() wants to receive.
    print("Boot playground")

    zprava()
