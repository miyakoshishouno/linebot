from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,TemplateSendMessage,ButtonsTemplate,URIAction
)
import os
import requests
import chart

app = Flask(__name__)

#環境変数取得
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]
YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]
TALKAPI_KEY = os.environ['YOUR_API']


line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(YOUR_CHANNEL_SECRET)

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'



if __name__ == "__main__":
    app.run()
    port = int(os.getenv("PORT"))
    app.run(host="0.0.0.0", port=port)



def talkapi(text):
   url = 'https://api.a3rt.recruit-tech.co.jp/talk/v1/smalltalk'
   req = requests.post(url, {'apikey':TALKAPI_KEY,'query':text}, timeout=5)
   data = req.json()

   if data['status'] != 0:
      return data['message']

   msg = data['results'][0]['reply']
   return msg


num = 0

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    push_text = event.message.text
    array = []
    global num

    if push_text == "チャート":
        num = 1
        # msg = chart.judge(push_text,num)
        msg = make_button_template()

        line_bot_api.reply_message(
            event.reply_token,
            msg
        )

    else:
        msg = talkapi(push_text)


    # if push_text != "チャート" and num > 0:
    #     if push_text == "Yes":
    #         num = num + 1
    #         msg = chart.judge(push_text,num)

    #     elif push_text == "No":
    #         num = num + 2
    #         msg = chart.judge(push_text,num)

    #     else:
    #         msg = "中断しました"
    #         num = 0

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=msg))


def make_button_template():
    message_template = TemplateSendMessage(
        alt_text="にゃーん",
        template=ButtonsTemplate(
            text="どこに表示されるかな？",
            # title="タイトルですよ",
            # image_size="cover",
            # thumbnail_image_url="https://example.com/gazou.jpg",
            actions=[
                URIAction(
                    label = "Yes",
                    text  = "yes"
                ),
                URIAction(
                    label = "No",
                    text  = "No"
                )
            ]
        )
    )
    return message_template