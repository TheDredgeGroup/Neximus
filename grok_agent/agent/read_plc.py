  echo from pycomm3 import LogixDriver > read_plc.py
   echo. >> read_plc.py
   echo # Your exact PLC IP and slot >> read_plc.py
   echo plc_ip = '192.168.68.252' >> read_plc.py
   echo plc_slot = 0  # Tweak if needed >> read_plc.py
   echo. >> read_plc.py
   echo try: >> read_plc.py
   echo     with LogixDriver(f'{plc_ip}/{plc_slot}') as plc: >> read_plc.py
   echo         value = plc.read('ai_test') >> read_plc.py
   echo         print(f"Current value of ai_test: {value.value}") >> read_plc.py
   echo except Exception as e: >> read_plc.py
   echo     print(f"Error reading tag: {e}") >> read_plc.py