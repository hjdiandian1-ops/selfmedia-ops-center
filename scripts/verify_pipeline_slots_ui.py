import asyncio
import os
from playwright.async_api import async_playwright

ARTIFACTS_DIR = "/Users/xiaowuliao/.gemini/antigravity/brain/ae4a3b30-c515-43f5-affa-649fcf998c34"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # 1. 访问首页并切换到流水线视图
        await page.goto("http://127.0.0.1:8787")
        await page.evaluate("localStorage.setItem('onboarding_done', '1'); if(window.skipOnboardingWizard) window.skipOnboardingWizard();")
        await page.wait_for_timeout(300)
        await page.wait_for_selector("#view-pipeline", state="attached")

        # 点击侧边栏或导航栏切换到流水线视图
        await page.evaluate("switchView('pipeline')")
        await page.wait_for_timeout(1000)

        # 截图 1: 流水线视图与顶部插槽工坊
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "pipeline_slots_workshop.png"))
        print("✅ Saved pipeline_slots_workshop.png")

        # 2. 点击更换小红书主编插槽
        await page.evaluate("openSlotPicker('xhs_editor')")
        await page.wait_for_timeout(600)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "pipeline_slot_picker_modal.png"))
        print("✅ Saved pipeline_slot_picker_modal.png")
        await page.evaluate("closeSlotPickerModal()")
        await page.wait_for_timeout(300)

        # 3. 切换到封面提示词库并打开一个封面详情模态弹窗
        await page.evaluate("switchView('cover-templates')")
        await page.wait_for_timeout(1000)
        await page.evaluate("openCoverModal('selfie-bag-sticker-cover')")
        await page.wait_for_timeout(600)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "cover_modal_linked_actions.png"))
        print("✅ Saved cover_modal_linked_actions.png")

        # 4. 点击套用模板建任务弹窗
        await page.evaluate("applyCoverTemplateToNewJob()")
        await page.wait_for_timeout(500)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "quick_adopt_modal_cover.png"))
        print("✅ Saved quick_adopt_modal_cover.png")
        await page.evaluate("closeQuickAdoptModal()")
        await page.evaluate("closeCoverModal()")
        await page.wait_for_timeout(300)

        # 5. 切换到 Skills 仓库并打开详情模态弹窗
        await page.evaluate("switchView('skills-repo')")
        await page.wait_for_timeout(1000)
        await page.evaluate("openSkillModal('human-writing')")
        await page.wait_for_timeout(600)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "skill_modal_linked_actions.png"))
        print("✅ Saved skill_modal_linked_actions.png")

        # 6. 点击挂载到插槽弹窗
        await page.evaluate("openMountSkillModal()")
        await page.wait_for_timeout(500)
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "mount_skill_to_slot_modal.png"))
        print("✅ Saved mount_skill_to_slot_modal.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
