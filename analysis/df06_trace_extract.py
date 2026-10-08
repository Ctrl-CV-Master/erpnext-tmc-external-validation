import re

log = open('analysis/formal_art/df06_fail.log'.replace('/', 'D:/tmc_erpnext_validation/analysis/') if False else 'D:/tmc_erpnext_validation/analysis/formal_art/df06_fail.log', encoding='utf-8', errors='ignore').read()
idx = log.find('Run dev task')
seg = log[idx:idx + 5000]
tb = re.search(r'Traceback[\s\S]{0,1500}', seg)
print(tb.group(0)[:1400] if tb else seg[-1400:])
