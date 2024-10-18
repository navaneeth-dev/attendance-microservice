import logging
from datetime import datetime

import pytesseract
from fastapi import FastAPI, HTTPException
from playwright.async_api import async_playwright
from pydantic import BaseModel

app = FastAPI()
logger = logging.getLogger("uvicorn.error")


class Subject(BaseModel):
    subject_code: str
    name: str
    percent: float


class StudentLogin(BaseModel):
    username: str
    password: str


class ScrapeResponse(BaseModel):
    student_name: str
    percent: float
    last_updated: str
    subjects: list[Subject]


@app.post("/scrape_attendance")
async def scrape_attendance(sl: StudentLogin) -> ScrapeResponse:
    scrape_res = await fetch_att(sl.username, sl.password)
    if scrape_res is None:
        raise HTTPException(status_code=500, detail="Scrape failure")

    return scrape_res


async def fetch_att(username, pwd, max_retries=3) -> ScrapeResponse:
    for _ in range(max_retries):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            page = await browser.new_page()
            login_url = (
                "http://184.95.52.42/velsonline/students/loginManager/youLogin.jsp"
            )
            await page.goto(login_url)

            # Fill the login form
            await page.fill('input[name="login"]', username)
            await page.fill('input[name="passwd"]', pwd)

            # Handle CAPTCHA
            captcha_image = page.locator("//img[@src='/velsonline/captchas']")
            await captcha_image.screenshot(path="captcha.png")
            captcha_text = pytesseract.image_to_string("captcha.png").strip()
            await page.fill('input[name="ccode"]', captcha_text)

            # Submit the login form
            await page.click("#_save")
            await page.wait_for_load_state("networkidle")

            # Check for "Invalid Captcha" error
            if await page.locator("td:has-text('Invalid Captcha')").count() > 0:
                await page.close()
                continue  # Retry login

            left_menu = page.frame_locator('frame[name="menu"]')
            student_name = await left_menu.locator(
                "#frmPageLeft > table > tbody > tr:nth-child(2) > td > b"
            ).text_content()
            if student_name is None:
                raise Exception("Student name not found")

            # Goto attendance page
            await left_menu.get_by_role("row", name="Attendance Details").click()
            await page.wait_for_load_state("networkidle")

            # fetch percent and end date
            att_frame = page.frame_locator('frame[name="content"]')
            percent = float(
                (
                    await att_frame.locator(
                        '#tblSubjectWiseAttendance tr.subtotal td:has-text("%")'
                    ).inner_text()
                ).strip()[:-1]
            )
            last_updated = await att_frame.locator(
                "#tblSubjectWiseAttendance tr.subheader1 td:nth-child(4)"
            ).inner_text()

            # Subject wise attendance
            subjects: list[Subject] = []
            rows = await att_frame.locator("#tblSubjectWiseAttendance > tbody tr").all()
            for i, row in enumerate(rows):
                # skip first 3 and last row (total percent)
                if i <= 3 or i == len(rows) - 1:
                    continue

                cells = await row.locator("td").all_text_contents()
                subject = Subject(
                    subject_code=cells[0],
                    name=cells[1],
                    percent=float(cells[5].strip()[:-1]),
                )
                subjects.append(subject)
                logger.info(f"{subject.subject_code} {subject.name} {subject.percent}")

            await page.close()
            await browser.close()

            date_obj = datetime.strptime(last_updated, "%d/%b/%Y")
            last_updated = date_obj.strftime("%d-%m-%Y")

            scrape_res = ScrapeResponse(
                student_name=student_name,
                percent=percent,
                last_updated=last_updated,
                subjects=subjects,
            )
            return scrape_res

    raise Exception("Failed to login after several attempts due to invalid captcha.")
