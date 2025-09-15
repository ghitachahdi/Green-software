import time, math, os
dur = int(os.getenv("DUR", "60"))
t0 = time.time(); x = 0.0
while time.time() - t0 < dur:
    for i in range(200_000):
        x += math.sin(i) * math.cos(i)
print("done", x)
