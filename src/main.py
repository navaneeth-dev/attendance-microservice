from fastapi import FastAPI
from pydantic import BaseModel
from playwright.async_api import async_playwright
import pytesseract
from datetime import datetime
import os
import logging


app = FastAPI()


class Item(BaseModel):
    name: str


@app.post("/scrape_attendance")
async def scrape_attendance(item: Item):
    student_name, percentage, end_date, subs, subs_percents = await fetch_att()
    print(percentage)
    return {"name": student_name}


async def fetch_att(username, pwd, max_retries=3):
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

            # Goto attendance page
            await left_menu.get_by_role("row", name="Attendance Details").click()
            await page.wait_for_load_state("networkidle")

            # Navigate to attendance page and fetch percentage and end date
            att_frame = page.frame_locator('frame[name="content"]')
            percentage = await att_frame.locator(
                '#tblSubjectWiseAttendance tr.subtotal td:has-text("%")'
            ).inner_text()
            end_date = await att_frame.locator(
                "#tblSubjectWiseAttendance tr.subheader1 td:nth-child(4)"
            ).inner_text()

            subs = await att_frame.locator(
                "#tblSubjectWiseAttendance > tbody td:nth-child(2)"
            ).all_inner_texts()
            subs = subs[2:-1]

            sub_percents = await att_frame.locator(
                "#tblSubjectWiseAttendance > tbody td:nth-child(6)"
            ).all_inner_texts()
            sub_percents = sub_percents[1:]
            logging.info(f"{subs}, {sub_percents}")

            await page.close()
            await browser.close()

            date_obj = datetime.strptime(end_date, "%d/%b/%Y")
            end_date = date_obj.strftime("%d-%m-%Y")

            return student_name, percentage, end_date, subs, sub_percents

    raise Exception("Failed to login after several attempts due to invalid captcha.")
