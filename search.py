﻿#!/usr/bin/python
from urllib.request import urlopen
from urllib import error
import re
from bs4 import BeautifulSoup
import csv

from openpyxl import Workbook
from werkzeug.utils import secure_filename
import os
import os.path
from flask import send_from_directory
import flask_excel as excel
from flask import Flask
from flask import request, render_template, redirect, url_for, jsonify
from openpyxl import load_workbook


UPLOAD_FOLDER = 'data'
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'csv', 'xls', 'xlsx', 'docx'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

#
# def allowed_file(filename):
#     return '.' in filename and \
#            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#
# @app.route('/up', methods=['GET', 'POST'])
# def upload_file():
#     if request.method == 'POST':
#         # check if the post request has the file part
#         if 'file' not in request.files:
#             return redirect(request.url)
#         file = request.files['file']
#         # if user does not select file, browser also
#         # submit a empty part without filename
#         if file.filename == '':
#             return redirect(request.url)
#         if file and allowed_file(file.filename):
#             filename = secure_filename(file.filename)
#             file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
#             return redirect(url_for('uploaded_file', filename=filename))
#     return '''
#     <!doctype html>
#     <title>Upload new File</title>
#     <h1>Upload new File</h1>
#     <form method=post enctype=multipart/form-data>
#       <p><input type=file name=file>
#          <input type=submit value=Upload>
#          <a href = "/upload"> LOOK File </a>
#     </form>
#     '''


# @app.route('/data/<filename>')
# def uploaded_file(filename):
#     return send_from_directory(app.config['UPLOAD_FOLDER'],
#                                filename)
#
#
# @app.route('/upload/', methods=['GET', 'POST'])
# def uploadu_file():
#     if request.method == 'POST':
#         return render_template('upfile.html',
#                                result_tab={"result": request.get_array(field_name='file', encoding="utf-8")})
#
#     return render_template('upfile.html')
#
#
# @app.route('/export', methods=['GET'])
# def export_records():
#     return excel.make_response_from_array([[1, 2], [3, 4]], 'xlsx',
#                                           file_name="file", encoding="ISO-8859-1")


@app.route('/app.js')
def sencha_app():
    return redirect(url_for('static', filename='app.js'))


def parse_links(links, visited, url):
    # убираем ссылки на на js и  css файлы
    timelist = []
    truelinks = []
    copy_links = links.copy()
    for link in copy_links:
        timelist.extend(link.split("/"))
        if ".js" in timelist[len(timelist) - 1].lower() or ".css" in timelist[len(timelist) - 1].lower():
            links.remove(link)
        elif "." in timelist[len(timelist) - 1].lower():
            timelist = timelist[len(timelist) - 1].lower().split(".")
            if "html" not in timelist and "php" not in timelist:
                links.remove(link)
        elif link in visited:
            links.remove(link)
        elif len(re.findall("[.,\-\s\?*\{\}\#]", timelist[len(timelist) - 1].lower())):
            links.remove(link)
        else:
            truelinks.append(link)
    # чистит список от ссылок на левые сайты (почти все)
    copy = truelinks.copy()
    for link in copy:
        if link.startswith("http://") or link.startswith("https://"):
            if not url.split("/")[2] == link.split("/")[2]:
                truelinks.remove(link)
            # и от самого себя
            elif url == link:
                truelinks.remove(link)
            elif not link.startswith(url):
                truelinks.remove(link)
        elif not link.startswith("//ww"):
            truelinks.append(url + link[1:])
            truelinks.remove(link)
        else:
            truelinks.remove(link)
    return truelinks


def get_links(html, url, visited):
    links = [link[0] for link in list(set(re.findall('"((http|ftp)s?://.*?)"', html)))]
    nonfull = list(set(re.findall('href="(.*?)"', html)))

    truelinks = parse_links(links, visited, url)
    truelinks2 = parse_links(nonfull, visited, url)

    truelinks2.extend(truelinks)
    truelinks2 = list(set(truelinks2))

    return truelinks2


def get_text(html, link):
    soup = BeautifulSoup(html, "lxml")

    # kill all script and style elements
    for script in soup(["script", "style"]):
        script.extract()  # rip it out

    # get all div
    div_saver = []
    for div in soup(["div"]):
        div = div.get_text()
        div_saver.append(div)

    div_saver2 = div_saver.copy()

    for idx, text in enumerate(div_saver2):
        # get text - если soup.body.get_text() - вернет только боди тд по аналогии
        # text = soup.get_text()

        # break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # drop blank lines
        text2 = link.join(chunk for chunk in chunks if chunk)
        div_saver.remove(text)
        div_saver.append(text2)

    return div_saver


def read_url(url):
    html = None
    with urlopen(url) as data:
        enc = data.info().get_content_charset('utf-8')
        try:
            html = data.read().decode(enc)
        except UnicodeDecodeError:
            print("bad unicode decoding")
    if html:
        return html


def find_words(url, text, words, posts):
    for word in words:
        if word in text:
            if url not in posts:
                pattern = re.compile(word, re.IGNORECASE)
                text = pattern.sub(word, text)
                posts.append((url, text))
    return posts


def main_alg(url, link, words, posts, visited_links, depth):
    if depth == 0:
        return posts
    try:
        # читаем ссылку и получаем ее html код
        html = read_url(link)
    except error.URLError as err:
        return posts
    # получаем строку с текстом в cсылке
    text_full = list(set(get_text(html, link)))
    # ищем слова и получаем назад список постов, где они были найдены
    for text in text_full:
        fwords = find_words(link, text, words, posts)
        if fwords and fwords[0] not in posts:
            posts.extend([list(set(fwords) - set(posts)), text])
        posts = list(set(posts))
        print("posts are found: {0}".format(len(posts)))
        # for post in posts:
        # print(post)
    # получаем все ссылки ресурса
    links = get_links(html, url, visited_links)

    links2 = []
    count = 0
    if len(links) > 10:
        while count < 10:
            links2.append(links[count])
            count += 1
    else:
        links2 = links
    for link in links2:
        try:
            visited_links.append(link)
            posts.extend(main_alg(url, link, words, posts, visited_links, depth - 1))
        except error.HTTPError as e:
            print("bad request")
    return posts


@app.route('/_findwords')
def add_numbers():
    #urls = request.args.get('url')
    a= execsear()
    urls=[]
    urls.extend(a[0])
    # word1 = request.args.get('word1')
    # word2 = request.args.get('word2')
    # word3 = request.args.get('word3')
    # value = ''
    words = []
    words.extend(a[1])

    # words = [str(word1), str(word2), str(word3)]
    # if len(word1.strip()) > 0:
    #    words.append(word1)
    # if len(word2.strip()) > 0:
    #    words.append(word2)
    # if len(word3.strip()) > 0:
    #    words.append(word3)
  # список найденных постов
    depth = 3  # размерность поиска вглубину (кол-во страниц сайта, которые мы просмотрим)
    if len(urls) > 1:
        for url in urls:
            posts = []
            visited_links = [url]  # was here
            if not url.startswith("http://") and not url.startswith("https://"):
                url = 'http://' + url
            if url[len(url)-1] == " ":
                url = del_probel(url)
            posts = set(main_alg(url, url, words, posts, visited_links, depth))
            wb = Workbook()
            ws = wb['data']
            for row in posts:
                ws.append(row)
            filename = 'static'+url + '.xlsx'
            wb.save(filename=filename)

            # with open('file.xlsx', 'w') as out:
            #     csv_out = csv.writer(out)
            #     csv_out.writerow(['link', 'text'])
            #     for row in posts:
            #         csv_out.writerow(row)
            # str_to_serv = ''
            # for post in posts:
            #     str_to_serv = str(post) + str_to_serv
            # return jsonify(result=str_to_serv)

def del_probel(url):
    url = url[:-1]
    if url[len(url) - 1] == " ":
       url = del_probel(url)
       return url
    else:
        return url

@app.route('/')
def index():
    return render_template('index.html')


def execsear(row=None):
    wb = load_workbook('static/test_check.xlsx')
    ws = wb['data']
    links = []
    words = []
    for col in ws['A']:
        if not col.value == None:
            links.append(col.value)
    for col in ws['B']:
        if not col.value == None:
            words.append(col.value)

    return [links, words]


def run(url, words):
    posts = []  # список найденных постов
    depth = 3  # размерность поиска вглубину (кол-во страниц сайта, которые мы просмотрим)
    visited_links = [url]  # was here
    print(url)
    print(words)
    posts = set(main_alg(url, url, words, posts, visited_links, depth))
    # with open('file.csv', 'w') as csvfile:
    #     spamwriter = csv.writer(csvfile,  delimiter=';',quotechar='|', quoting=csv.QUOTE_MINIMAL, dialect='excel')
    #     spamwriter.writerow(posts)
    with open('file.csv', 'w') as out:
        csv_out = csv.writer(out)
        csv_out.writerow(['link', 'text'])
        for row in posts:
            csv_out.writerow(row)
            # print(posts)


if __name__ == '__main__':
    # включает веб морду
    app.run()
    # для тестов без веб-морды
    # run('http://toyota-axsel.com', ["price"])
