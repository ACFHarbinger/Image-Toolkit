from hie_middleware.restore_cli import build_parser


def test_restore_cli_parses_deblur_and_inpaint_commands():
    parser = build_parser()
    deblur = parser.parse_args(["deblur", "blurred.png", "--strength", "1.5"])
    assert deblur.operation == "deblur"
    assert deblur.strength == 1.5
    inpaint = parser.parse_args(["inpaint", "owned.png", "--mask", "mask.png", "--permission-confirmed"])
    assert inpaint.operation == "inpaint"
    assert inpaint.permission_confirmed is True
