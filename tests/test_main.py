import json

import main


class FakePort:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


class FakeButton:
    instances = []

    def __init__(self, pin, **kwargs):
        self.pin = pin
        self.kwargs = kwargs
        self.when_pressed = None
        self.when_released = None
        self.instances.append(self)


def test_find_target_input_matches_case_insensitively():
    assert main.find_target_input(["MIDI Keyboard", "PiSound MIDI"]) == "PiSound MIDI"
    assert main.find_target_input(["MIDI Keyboard"]) is None


def test_open_midi_outputs_retries_until_modep_input_is_available():
    primary = FakePort()
    routed = FakePort()
    input_names = iter([[], ["MODEP MIDI"]])
    sleeps = []

    midi_out, midi_connect = main.open_midi_outputs(
        open_output=lambda name, virtual=False: primary if virtual else routed,
        get_input_names=lambda: next(input_names),
        sleep=sleeps.append,
    )

    assert midi_out is primary
    assert midi_connect is routed
    assert sleeps == [main.MIDI_TARGET_RETRY_DELAY]


def test_cc_press_toggles_and_sends_to_both_ports(monkeypatch):
    primary = FakePort()
    routed = FakePort()
    states = {20: False}
    feedback = []
    monkeypatch.setattr(main, "publish_feedback", feedback.append)

    main.handle_cc_press(6, 20, "Effect Toggle 1", primary, routed, states)
    main.handle_cc_press(6, 20, "Effect Toggle 1", primary, routed, states)

    assert [message.value for message in primary.messages] == [127, 0]
    assert [message.control for message in routed.messages] == [20, 20]
    assert states[20] is False
    assert feedback == [
        "Effect Toggle 1: MIDI Ch 1 | CC 20 | 127 (ON)",
        "Effect Toggle 1: MIDI Ch 1 | CC 20 | 0 (OFF)",
    ]


def test_publish_feedback_writes_timestamped_json(tmp_path):
    feedback_file = tmp_path / "feedback.json"

    main.publish_feedback("Next", str(feedback_file), timestamp=10.0)

    assert json.loads(feedback_file.read_text()) == {"message": "Next", "timestamp": 10.0}


def test_command_press_starts_bash_script():
    calls = []

    main.handle_cmd_press(23, "/tmp/next.sh", "Next Pedalboard", calls.append)

    assert calls == [["/bin/bash", "/tmp/next.sh"]]


def test_register_buttons_binds_each_pin_configuration(monkeypatch):
    FakeButton.instances.clear()
    configs = {
        6: {"name": "Effect", "type": "cc", "val": 20},
        23: {"name": "Next", "type": "cmd", "val": "/tmp/next.sh"},
    }
    buttons = main.register_buttons(FakePort(), None, FakeButton, configs)

    assert [button.pin for button in buttons] == [6, 23]
    assert buttons[0].when_pressed(None) is None

    calls = []
    monkeypatch.setattr(main, "handle_cmd_press", lambda *args: calls.append(args))
    buttons[1].when_pressed(None)
    assert calls == [(23, "/tmp/next.sh", "Next")]
