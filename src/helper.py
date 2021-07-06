import broadlink, base64
devices = broadlink.discover(timeout=2)
device = devices[0]
device.auth()
device.enter_learning()
input("Wait:")
ir_command = device.check_data()
print(type(ir_command), ir_command)
print(base64.b64encode(ir_command))