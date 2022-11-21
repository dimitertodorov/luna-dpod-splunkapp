import time


timeform = "2022-11-17 05:59:19.046662 UTC"
format = '%Y-%m-%d %H:%M:%S.%f %Z'

vv = time.strptime(timeform,format)
print(vv)