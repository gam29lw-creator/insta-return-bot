
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/") {
      return new Response("InstaReturn Monitor is running!");
    }

    if (url.pathname === "/webhook" && request.method === "POST") {
      const secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token");

      if (secret !== env.WEBHOOK_SECRET) {
        return new Response("Unauthorized", { status: 401 });
      }

      const update = await request.json();
      const message = update.message;

      if (message?.text) {
        const chatId = message.chat.id;
        const text = message.text.trim();

        let reply = "الأمر غير معروف. أرسل /help";

        if (text === "/start" || text === "/help") {
          reply =
            "أهلاً بيك في InstaReturn Monitor\n\n" +
            "/add username - إضافة حساب\n" +
            "/list - عرض الحسابات\n" +
            "/remove username - حذف حساب";
        }

        await fetch(
          `https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              text: reply
            })
          }
        );
      }

      return new Response("OK");
    }

    return new Response("Not found", { status: 404 });
  }
};
