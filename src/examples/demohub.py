import asyncio
import os
import uuid

import cv2
import numpy as np
import pynng

from wigglecam.dto import ImageMessage


async def main():
    # host subscribes to all devices, need to have the ips then?!
    sub_lo = pynng.Sub0()  # Pipeline pull for lores stream.
    sub_lo.subscribe(b"")
    # block=False means continue program and try to connect in the background without any exception
    sub_lo.listen("tcp://0.0.0.0:5556")  # , block=False)

    sub_hi = pynng.Sub0()  # Pipeline pull for lores stream.
    sub_hi.subscribe(b"")
    sub_hi.recv_timeout = 1000
    # block=False means continue program and try to connect in the background without any exception
    sub_hi.listen("tcp://0.0.0.0:5557")  # , block=False)

    # host also subscribes to the hires replies
    pub_trigger = pynng.Pub0()
    # surveyor_hi.survey_time = 1000
    # block=False means continue program and try to connect in the background without any exception
    pub_trigger.listen("tcp://0.0.0.0:5555")  # , block=False)

    lores_frames = {}
    trigger = asyncio.Event()

    async def lores_task():
        nonlocal lores_frames
        while True:
            data = await sub_lo.arecv()
            msg = ImageMessage.from_bytes(data)

            img = cv2.imdecode(np.frombuffer(msg.jpg_bytes, np.uint8), cv2.IMREAD_COLOR)
            lores_frames[msg.device_id] = img

    async def hires_task():
        base_dir = "job_results"
        os.makedirs(base_dir, exist_ok=True)

        while True:
            await trigger.wait()
            trigger.clear()

            print("Job start")

            # Eindeutige ID für diese Umfrage
            job_uuid = uuid.uuid4()
            await pub_trigger.asend(job_uuid.bytes)

            job_folder = os.path.join(base_dir, f"job_{job_uuid}")
            os.makedirs(job_folder, exist_ok=True)
            results_no = 0

            while True:
                try:
                    data = await sub_hi.arecv()
                    msg = ImageMessage.from_bytes(data)
                    results_no += 1

                    if msg.job_id != job_uuid:
                        # Antwort gehört zu alter Umfrage -> ignorieren
                        print("warning, old job id result received, ignored!")
                        continue

                    fname = f"cam{msg.device_id}.jpg"
                    with open(os.path.join(job_folder, fname), "wb") as f:
                        f.write(msg.jpg_bytes)

                except pynng.exceptions.Timeout:
                    print(f"job finished after 1s no more data, got {results_no} result!")
                    break

    async def ui_task():
        nonlocal lores_frames
        while True:
            if lores_frames:
                imgs = [lores_frames[cid] for cid in sorted(lores_frames.keys())]
                h = 240
                imgs_resized = [cv2.resize(img, (320, h)) for img in imgs]
                rows = []
                for i in range(0, len(imgs_resized), 2):
                    row_imgs = imgs_resized[i : i + 2]
                    if len(row_imgs) == 1:
                        # pad with a black image of same size
                        blank = np.zeros_like(row_imgs[0])
                        row_imgs.append(blank)
                    row = cv2.hconcat(row_imgs)
                    rows.append(row)

                wall = cv2.vconcat(rows)
                cv2.imshow("Live Wall", wall)

            key = cv2.waitKey(1)
            if key == 27:  # ESC
                break
            elif key == ord("t"):
                trigger.set()

            await asyncio.sleep(0.05)

    await asyncio.gather(lores_task(), hires_task(), ui_task())


def run_async():
    asyncio.run(main())


if __name__ == "__main__":
    run_async()
