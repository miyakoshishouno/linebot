from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,TemplateSendMessage,ConfirmTemplate,\
        MessageAction,DatetimePickerAction,PostbackEvent,ButtonsTemplate,PostbackTemplateAction,\
            QuickReply, QuickReplyButton,PostbackAction
)

import re
import psycopg2
from psycopg2.extras import DictCursor
import os
import requests
import datetime
from datetime import time

app = Flask(__name__)

#環境変数取得
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]
YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]
TALKAPI_KEY = os.environ['YOUR_API']
DATABASE_URL = os.environ.get('DATABASE_URL')

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


# 日常会話API
def talkapi(text):
   url = 'https://api.a3rt.recruit-tech.co.jp/talk/v1/smalltalk'
   req = requests.post(url, {'apikey':TALKAPI_KEY,'query':text}, timeout=5)
   data = req.json()

   if data['status'] != 0:
      return data['message']

   msg = data['results'][0]['reply']
   return msg



@handler.add(MessageEvent, message=TextMessage)
# テキスト別に条件分岐
def handle_message(event):
    profile = line_bot_api.get_profile(event.source.user_id)
    push_text = event.message.text

    # ユーザ情報取得
    row = get_user_id(profile.user_id[:5])

    # 初めて取得するuser_idであれば登録
    if len(row) == 0:
        add_user_id(profile.user_id[:5])
        row = get_user_id(profile.user_id[:5])
        user_id = row[0]
    else:
        user_id = row[0]

    # フェーズの確認
    rows = select_phase(user_id)

    # フェーズが(備考段階)かどうか
    if rows[0] == 3:
        # if rows[0] == 3:
        yoyaku_id = get_yoyaku_id_in_phase(user_id)
        add_yoyaku_note(push_text,user_id,yoyaku_id[0])
        label = '備考：' + push_text + '\nで保存しました。\n予約状況は、以下で確認できます。'
        msg = button_menu(label)

        line_bot_api.reply_message(
            event.reply_token,
            msg
        )

    elif rows == 1 or rows == 2:
        del_phase_record(user_id)
        msg = "予約処理を中断しました。"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=msg))

    else:
        if "予約" in push_text:
            question = "予約しますか？"
            msg = button_yoyaku(question)
            line_bot_api.reply_message(
                event.reply_token,
                msg
            )

        else:
            msg = talkapi(push_text)

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg))


# ―――――――――――　db処理　―――――――――――

# db接続
def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')



# ユーザID一覧取得処理
def get_user_id(user_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT id FROM user_table WHERE user_id = (%s)",(user_id,))
            rows = cur.fetchone()
            return rows



# ユーザID登録処理
def add_user_id(user_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("INSERT INTO user_table VALUES((select (COALESCE(max(id),0)+1) from user_table),%s)",(str(user_id),))
            conn.commit()

    

# 予約一覧表示処理
def get_response_message(user_id):
    get_day = datetime.datetime.now() 
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM yoyaku_table WHERE user_id = (%s) AND fixed = 1 ORDER BY yoyaku_date DESC LIMIT 5",(str(user_id),))
            rows = cur.fetchall()
            return rows


# 日付&備考取得
def get_message(yoyaku_id):
    get_day = datetime.datetime.now() 
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT yoyaku_date,note FROM yoyaku_table WHERE id = (%s)",(yoyaku_id,))
            rows = cur.fetchone()
            return rows



# 削除処理
def del_response_message(yoyaku_id,user_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("DELETE FROM yoyaku_table WHERE id = (%s) AND user_id = (%s)",(yoyaku_id,str(user_id)))
            conn.commit()



# 空insert→段階update
def yoyaku_table_insert(user_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("DELETE FROM yoyaku_table WHERE fixed = 0 AND user_id = (%s)",(str(user_id),))            
            cur.execute("INSERT INTO yoyaku_table (id,user_id,fixed)\
                 VALUES((SELECT COALESCE(max(id),0)+1 FROM yoyaku_table),%s,0)",(str(user_id),))
            conn.commit()



# id取得
def get_yoyaku_id(user_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT setval('id_code_seq',MAX(id)) FROM yoyaku_table WHERE user_id = %s",(str(user_id),))
            rows = cur.fetchone()
            return rows



# phaseレコード作成
def phase_table_insert(user_id,yoyaku_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("INSERT INTO phase_table (id,user_id,yoyaku_phase,yoyaku_id)\
                 VALUES((SELECT COALESCE(max(id),0)+1 FROM phase_table),%s,0,%s)"\
                     ,(str(user_id),yoyaku_id))
            conn.commit()



# 新規登録時、中断されているphaseを削除
def del_phase_record(user_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("DELETE FROM phase_table WHERE user_id = (%s)",(str(user_id),))
            conn.commit()



# 日付追加
def add_yoyaku_ymd(yoyaku_day,yoyaku_id,user_id):
     with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("UPDATE yoyaku_table SET yoyaku_date = (%s)\
                WHERE id = (%s)",(yoyaku_day,yoyaku_id)),
            cur.execute("UPDATE phase_table SET yoyaku_phase = 1 WHERE yoyaku_id = %s AND user_id = %s"\
                ,(yoyaku_id,str(user_id)))
            conn.commit()



# 日付取得
def get_yoyaku_day(yoyaku_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT yoyaku_date FROM yoyaku_table WHERE id = %s",(yoyaku_id,))
            rows = cur.fetchone()
            return rows



# 時刻追加
def add_yoyaku_time(yoyaku_day,yoyaku_id,user_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("UPDATE yoyaku_table SET yoyaku_date = (%s),fixed = 1\
                WHERE id = %s",(yoyaku_day,yoyaku_id))
            cur.execute("UPDATE phase_table SET yoyaku_phase = 2 WHERE yoyaku_id = %s AND user_id = %s"\
                ,(yoyaku_id,str(user_id)))
            conn.commit()



# フェーズ取得
def select_phase(user_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT max(yoyaku_phase) FROM phase_table WHERE user_id = (%s)",(str(user_id),))
            rows = cur.fetchone()
            return rows



# フェーズ更新
def update_yoyaku_phase(yoyaku_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("UPDATE phase_table SET yoyaku_phase = 3 WHERE yoyaku_id = (%s)",(yoyaku_id,))
            conn.commit()



# フェーズでyoyaku_id取得
def get_yoyaku_id_in_phase(user_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT yoyaku_id FROM phase_table WHERE user_id = (%s) AND yoyaku_phase = 3",(str(user_id),))
            rows = cur.fetchone()
            return rows



# 備考更新
def add_yoyaku_note(push_text,user_id,yoyaku_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("UPDATE yoyaku_table SET note = (%s) WHERE user_id = (%s) AND id = \
                (SELECT yoyaku_id FROM phase_table WHERE yoyaku_id = %s)",(push_text,str(user_id),yoyaku_id))
            cur.execute("DELETE FROM phase_table WHERE user_id = (%s)",(str(user_id),))
            conn.commit()



# 日時処理(編集)
def change_yoyaku_day(yoyaku_day,user_id,yoyaku_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("UPDATE yoyaku_table SET yoyaku_date = (%s) WHERE user_id = (%s) AND id = %s",\
                (yoyaku_day,str(user_id),yoyaku_id))
            conn.commit()



# 備考取得
def get_yoyaku_note(yoyaku_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT note FROM yoyaku_table WHERE id = (%s)",(yoyaku_id,))
            rows = cur.fetchone()
            return rows



# 備考処理(編集)
def change_yoyaku_note(push_text,user_id,yoyaku_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("UPDATE yoyaku_table SET note = (%s) WHERE user_id = (%s) AND id = \
                (SELECT yoyaku_id FROM phase_table WHERE yoyaku_id = %s)",(push_text,str(user_id),yoyaku_id))
            cur.execute("DELETE FROM phase_table WHERE user_id = (%s)",(str(user_id),))
            conn.commit()

# ――――――――――――――――――――――――――――

# ――――――――　ボタン処理　――――――――

# 予約ボタン
def button_yoyaku(question):
    message_template = TemplateSendMessage(
        alt_text="a",
        template=ConfirmTemplate(
            text=question,
            actions=[
                PostbackAction(
                    label = "新規予約",
                    data  = "create_yoyaku"
                ),
                PostbackAction(
                    label = "予約状況確認",
                    data  = "menu_yoyaku"
                )
            ]
        )
    )
    return message_template



# 各項目ボタン
def button_menu(label):
    message_template = TemplateSendMessage(
        alt_text="a",
        template=ButtonsTemplate(
            text=label,
            actions=[
                PostbackAction(
                    label = "予約一覧",
                    data  = "show_yoyaku"
                ),
                PostbackAction(
                    label = "予約変更",
                    data  = "change_yoyaku"
                ),
                PostbackAction(
                    label = "予約削除",
                    data  = "del_yoyaku"
                )
            ]
        )
    )
    return message_template



# 日付ボタン
def button_yoyaku_ymd(label):
    # 現在日時の取得
    get_day = datetime.datetime.now()
    
    if get_day.hour + 9 > 18:
        get_date = str(get_day.year) + "-" + str(get_day.month).zfill(2) + "-" + str(get_day.day + 1).zfill(2)
        max_date = str(get_day.year) + "-" + str(get_day.month + 1 ).zfill(2) + "-" + str(get_day.day + 1).zfill(2)
    else:
        get_date = str(get_day.year) + "-" + str(get_day.month).zfill(2) + "-" + str(get_day.day).zfill(2)
        max_date = str(get_day.year) + "-" + str(get_day.month + 1 ).zfill(2) + "-" + str(get_day.day).zfill(2)


    message_template = TemplateSendMessage(
        alt_text="a",
        template=ConfirmTemplate(
            text=label,
            actions=[
                DatetimePickerAction(
                    type = "datetimepicker",
                    label = "日付選択",
                    data = "select_day_yoyaku",
                    mode = "date",
                    initial = get_date,
                    max = max_date,
                    min = get_date
                ),
                PostbackAction(
                    label = "予約状況確認",
                    data  = "menu_yoyaku"
                )
            ]
        )
    )
    return message_template



# 時刻選択ボタン
def button_yoyaku_time(select_day):
    # 現在日時の取得
    get_day = datetime.datetime.now()
    get_now = str(get_day.year) +'/' +  str(get_day.month).zfill(2) + '/' + str(get_day.day).zfill(2)
    get_date = str(get_day.hour + 9).zfill(2) + ":00:00"
    # 時間によってボタンの数を変更
    item_list = []
    time_list = [10,11,12,13,14,15,16,17,18,19]

    #当日の場合
    if select_day == get_now:
        for i in range(len(time_list)):
            if time(int(str(get_day.hour + 9 + 1).zfill(2)),00,00) < time(time_list[i],00,00):
                item_list.append(QuickReplyButton(\
                    action=PostbackAction(label= str(time_list[i]) + ":00~", data= "add_time_" + str(time_list[i]) + ":00")))

    else:
        for i in range(len(time_list)):
            item_list.append(QuickReplyButton(\
                action=PostbackAction(label= str(time_list[i]) + ":00~", data= "add_time_" + str(time_list[i]) + ":00")))

    quick_reply=QuickReply(items = item_list)
    return quick_reply



# 削除確認ボタン
def button_del_kakunin(user_id):
    rows = get_response_message(user_id)
    item_list = []
    if len(rows):
        for i in range(len(rows)):
            r = rows[i]
            item_list.append(QuickReplyButton(\
                action=PostbackAction(label= (str(r[1]).replace('-','/'))[:-3], data= "del_id_" + str(r[0]))))

        item_list.append(QuickReplyButton(\
            action=PostbackAction(label= "戻る", data= "cancel")))

    quick_reply=QuickReply(items = item_list)
    return quick_reply



# 編集確認ボタン
def button_change_kakunin(user_id):
    rows = get_response_message(user_id)
    item_list = []
    if len(rows):
        for i in range(len(rows)):
            r = rows[i]
            item_list.append(QuickReplyButton(\
                action=PostbackAction(label= (str(r[1]).replace('-','/'))[:-3], data= "change_id_" + str(r[0]))))

        item_list.append(QuickReplyButton(\
            action=PostbackAction(label= "戻る", data= "cancel")))

    quick_reply=QuickReply(items = item_list)
    return quick_reply


# 備考入力確認ボタン
def button_note_yoyaku(label):
    message_template = TemplateSendMessage(
        alt_text="a",
        template=ButtonsTemplate(
            text=label,
            actions=[
                PostbackAction(
                    label = "続けて備考を入力する",
                    data  = "create_note_yoyaku"
                ),
                PostbackAction(
                    label = "備考を入力せず終了する",
                    data  = "end_yoyaku"
                )
            ]
        )
    )
    return message_template



# 編集項目ボタン
def button_change_yoyaku(label,yoyaku_id,day):
    get_day = datetime.datetime.now()
    
    if (get_day.hour + 9 ) > 18:
        get_date = str(get_day.year) + "-" + str(get_day.month).zfill(2) + "-" + str(get_day.day + 1).zfill(2)
        max_date = str(get_day.year) + "-" + str(get_day.month + 1).zfill(2) + "-" + str(get_day.day + 1).zfill(2)
    else:
        get_date = str(get_day.year) + "-" + str(get_day.month).zfill(2) + "-" + str(get_day.day).zfill(2)        
        max_date = str(get_day.year) + "-" + str(get_day.month + 1).zfill(2) + "-" + str(get_day.day).zfill(2)

    if day <= get_date:
        day = get_date

    message_template = TemplateSendMessage(
        alt_text="a",
        template=ButtonsTemplate(
            text=label,
            actions=[
                DatetimePickerAction(
                    type = "datetimepicker",
                    label = "日付を変更する",
                    data = "change_yoyaku_day_" + str(yoyaku_id),
                    mode = "date",
                    initial = day,
                    max = max_date,
                    min = get_date
                ),
                PostbackAction(
                    label = "時刻を変更する",
                    data  = "change_yoyaku_time_" + str(yoyaku_id)
                ),
                PostbackAction(
                    label = "備考を修正する",
                    data  = "change_yoyaku_note_" + str(yoyaku_id)
                ),
                PostbackAction(
                    label = "予約状況一覧に戻る",
                    data  = "cancel"
                )
            ]
        )
    )
    return message_template



# 時刻ボタン(編集)
def change_button_yoyaku_time(before_ymd,yoyaku_id):
    # 現在日時の取得
    get_day = datetime.datetime.now()
    get_now = str(get_day.year) +'/' +  str(get_day.month).zfill(2) + '/' + str(get_day.day).zfill(2)
    get_date = str(get_day.hour + 9).zfill(2) + ":00:00"
    # 時間によってボタンの数を変更
    item_list = []
    time_list = [10,11,12,13,14,15,16,17,18,19]

    #当日の場合
    if before_ymd == get_now:
        for i in range(len(time_list)):
            if time(int(str(get_day.hour + 9 + 1).zfill(2)),00,00) < time(time_list[i],00,00):
                item_list.append(QuickReplyButton(\
                    action=PostbackAction(label= str(time_list[i]) + ":00~", data= "change_time_" + str(time_list[i]) + "," +  yoyaku_id)))

    else:
        for i in range(len(time_list)):
            item_list.append(QuickReplyButton(\
                action=PostbackAction(label= str(time_list[i]) + ":00~", data= "change_time_" + str(time_list[i]) + "," +  yoyaku_id)))

    quick_reply=QuickReply(items = item_list)
    return quick_reply

# ―――――――――――――――――――――――

# ボタン押下時イベント
@handler.add(PostbackEvent)
def on_postback(event):
    # ユーザId取得
    profile = line_bot_api.get_profile(event.source.user_id)
    row = get_user_id(profile.user_id[:5])
    user_id = row[0]
    yoyaku_id = get_yoyaku_id(user_id)

    if isinstance(event, PostbackEvent):
        if event.postback.data is not None:
            # 「新規予約」押下時
            if event.postback.data == 'create_yoyaku':
                yoyaku_table_insert(user_id)
                del_phase_record(user_id)
                yoyaku_id = get_yoyaku_id(user_id)
                phase_table_insert(user_id,yoyaku_id[0])

                label = "日付を選択してください。"
                msg  = button_yoyaku_ymd(label)
                line_bot_api.reply_message(
                    event.reply_token,
                    msg
                )

            # 「予約状況確認」押下時
            elif event.postback.data == 'menu_yoyaku':

                label = "該当する項目を選択してください。"
                msg = button_menu(label)
                line_bot_api.reply_message(
                    event.reply_token,
                    msg
                )


            # 「予約一覧」押下時
            elif event.postback.data == 'show_yoyaku':
                rows = get_response_message(user_id)

                if len(rows)==0:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text='現在予約はありません。'))
                else:
                    reply_message = '現在の予約状況は以下になります。(最新5件を表示)'
                    for i in range(len(rows)):
                        r = rows[i]
                        reply_message += '\n\n予約状況 :' + (str(r[1]).replace('-','/'))[:-3] + '\n備考 :' + r[2]

                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=reply_message))


            # 「予約削除」押下時
            elif event.postback.data == 'del_yoyaku':
                label = "削除する項目を選択してください。(最新5件を表示)"
                msg = button_del_kakunin(user_id)
                if len(msg.items) != 0:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=label,quick_reply=msg)
                    )
                else:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text='現在予約はありません。'))
                        

            # 「日付選択」押下時(新規)
            elif event.postback.data == 'select_day_yoyaku':
                get_day = (event.postback.params['date'])[:4] + "/" + (event.postback.params['date'])[5:7] + "/" + (event.postback.params['date'])[8:]
                label = (get_day + "ですね。\n希望する時間帯を選択して下さい。")
                add_day = get_day + " " + "00:00:00"
                add_yoyaku_ymd(add_day,yoyaku_id[0],user_id)

                msg  = button_yoyaku_time(get_day)
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=label,quick_reply=msg)
                )


            # 時刻選択時(新規)
            elif event.postback.data.startswith('add_time_'):
                yoyaku_data = str(event.postback.data)[9:] + ":00"
                row = get_yoyaku_day(yoyaku_id[0])
                yoyaku_day = str(row[0]).replace('00:00:00',yoyaku_data)
                add_yoyaku_time(yoyaku_day,yoyaku_id[0],user_id)
                
                label = yoyaku_day[:-3].replace('-','/') + "で\n予約を完了しました。\n予約状況は、予約一覧から\n確認できます。"
                msg = button_note_yoyaku(label)

                line_bot_api.reply_message(
                    event.reply_token,
                    msg
                )
            

            #「続けて備考を入力する」押下時
            elif event.postback.data == 'create_note_yoyaku':
                update_yoyaku_phase(yoyaku_id[0])

                label = "備考を入力してください。"
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=label)
                )
            

            # 「備考を入力せず終了する」押下時
            elif event.postback.data == 'end_yoyaku':
                del_phase_record(user_id)

                label = "ご利用ありがとうございました。"
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=label)
                )


            # 「予約状況一覧に戻る」押下時
            elif event.postback.data == 'cancel':

                    label = "該当する項目を選択してください。"
                    msg = button_menu(label)
                    line_bot_api.reply_message(
                        event.reply_token,
                        msg
                    )


            # 「予約変更」押下時
            elif event.postback.data == 'change_yoyaku':
                label = "変更する予約を選択してください。(最新5件を表示)"
                msg = button_change_kakunin(user_id)

                if len(msg.items) != 0:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=label,quick_reply=msg)
                    )

                else:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text='現在予約はありません。'))
            

            # 日付選択時(削除)
            elif event.postback.data.startswith('del_id_'):
                yoyaku_id = event.postback.data[7:]
                del_response_message(yoyaku_id,user_id)

                label = "削除が完了しました。"
                msg = button_menu(label)

                line_bot_api.reply_message(
                    event.reply_token,
                    msg
                )


            # 日付選択時(編集)
            elif event.postback.data.startswith('change_id_'):
                row = get_message(event.postback.data[10:])
                yoyaku_id = event.postback.data[10:]
                day = str(row[0])[:10]

                label = '変更する項目を選択してください。\n現在の予約状況：\n' + str(row[0])[:-3].replace('-','/') + '\n備考：' + row[1]
                msg = button_change_yoyaku(label,yoyaku_id,day)

                line_bot_api.reply_message(
                    event.reply_token,
                    msg
                )


            # 日付を変更する(編集)
            elif event.postback.data.startswith('change_yoyaku_day_'):
                # 現在の日付取得
                get_now = datetime.datetime.now()
                get_today = str(get_now.year) + "/" + str(get_now.month).zfill(2) + "/" + str(get_now.day).zfill(2) + " " + str(get_now.hour + 9 + 1).zfill(2) + ":00:00"
                get_day = (event.postback.params['date'])[:4] + "/" + (event.postback.params['date'])[5:7] + "/" + (event.postback.params['date'])[8:]

                yoyaku_id = event.postback.data[18:]
                before_day = get_yoyaku_day(yoyaku_id)
                get_time = str((before_day[0]).hour).zfill(2) +  ":" + str((before_day[0]).minute).zfill(2) + ":00"
                cahange_date = get_day + " " + get_time
                change_yoyaku_day(cahange_date,user_id,yoyaku_id)

                if datetime.datetime.strptime(get_today, "%Y/%m/%d %H:%M:%S") >= datetime.datetime.strptime(cahange_date, "%Y/%m/%d %H:%M:%S"):
                    label = "過去の時刻に設定されているため、時刻を変更してください。\n変更前予約時刻：" + str(before_day[0].hour).zfill(2) + ":00~"
                    msg = change_button_yoyaku_time(get_day,yoyaku_id)

                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=label,quick_reply=msg)
                    )

                else:
                    label = cahange_date[:-3] + "で予約の変更が完了しました。\n予約状況は、予約一覧から\n確認できます。"
                    msg = button_menu(label)

                    line_bot_api.reply_message(
                        event.reply_token,
                        msg
                    )


            # 「時刻を変更する」押下時
            elif event.postback.data.startswith('change_yoyaku_time_'):
                yoyaku_id = event.postback.data[19:]
                before_day = get_yoyaku_day(yoyaku_id)
                before_ymd = str((before_day[0]).year) + "/" + str((before_day[0]).month).zfill(2) + "/" + str((before_day[0]).day).zfill(2)
                label = "変更後の時刻を選択してください。\n変更前予約時刻：" + str(before_day[0].hour).zfill(2) + ":" + str(before_day[0].minute).zfill(2) + "~"
                msg = change_button_yoyaku_time(before_ymd,yoyaku_id)

                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=label,quick_reply=msg)
                )


            # 「備考を修正する」押下時
            elif event.postback.data.startswith('change_yoyaku_note_'):
                yoyaku_id = event.postback.data[19:]
                phase_table_insert(user_id,yoyaku_id)
                update_yoyaku_phase(yoyaku_id)
                before_note = get_yoyaku_note(yoyaku_id)
                label = "備考を入力してください。\n変更前：" + before_note[0]

                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=label)
                )


            # 変更後時刻選択時(編集)
            elif event.postback.data.startswith('change_time_'):
                yoyaku_id = event.postback.data[15:]
                day = get_yoyaku_day(yoyaku_id)
                new_day = str(day[0].replace(hour = int(event.postback.data[12:14])))
                change_yoyaku_day(new_day,user_id,yoyaku_id)

                label = (new_day[:-3]).replace('-','/') + "で予約の変更が完了しました。\n予約状況は、予約一覧から\n確認できます。"
                msg = button_menu(label)

                line_bot_api.reply_message(
                    event.reply_token,
                    msg
                )