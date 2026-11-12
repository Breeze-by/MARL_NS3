"""Convert the existing Chinese Markdown; paginate tall figures by panel row."""
from pathlib import Path
from html import escape
import re
import shutil
from urllib.parse import unquote

import mistune
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, Table,
                               TableStyle, KeepTogether, PageBreak)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE/'通信方式对比图表汇总.md'
TEMP = ROOT/'tmp/pdfs/communication-summary'
OUTPUT = ROOT/'output/pdf/通信方式对比图表汇总.pdf'
SIZE = landscape(A4)
WIDTH = SIZE[0]-76
FONT = 'ChineseBody'


def inline(nodes):
    result=[]
    for node in nodes:
        kind=node['type']
        if kind=='text':
            result.append(escape(node['raw']))
        elif kind=='strong':
            result.append('<b><font color="#21455F">'+inline(node['children'])+'</font></b>')
        elif kind=='emphasis':
            result.append('<i>'+inline(node['children'])+'</i>')
        elif kind=='codespan':
            result.append('<font color="#47556A">'+escape(node['raw'])+'</font>')
        elif kind=='link':
            # Source labels remain legible; repository-local links also remain local.
            url=node['attrs']['url']
            if not re.match(r'^[a-zA-Z]+:',url):
                url=(HERE/unquote(url)).resolve().as_uri()
            result.append('<link href="'+escape(url,quote=True)+'" color="#287297">'+inline(node['children'])+'</link>')
        elif kind in ('softbreak','linebreak'):
            result.append('<br/>')
        else:
            result.append(inline(node.get('children',[])))
    return ''.join(result).replace('—','-').replace('–','-').replace('‑','-')


def styles():
    common=dict(fontName=FONT,wordWrap='CJK',textColor=colors.HexColor('#263747'))
    return {
        'body':ParagraphStyle('body',fontSize=10.2,leading=15.3,spaceAfter=7,**common),
        'title':ParagraphStyle('title',fontSize=22,leading=31,spaceAfter=18,keepWithNext=True,**common),
        'h2':ParagraphStyle('h2',fontSize=15.5,leading=23,spaceBefore=14,spaceAfter=9,keepWithNext=True,**common),
        'h3':ParagraphStyle('h3',fontSize=12.3,leading=19,spaceBefore=11,spaceAfter=7,keepWithNext=True,**common),
        'caption':ParagraphStyle('caption',fontSize=11,leading=17,spaceBefore=4,spaceAfter=7,alignment=TA_CENTER,**common),
        'note':ParagraphStyle('note',fontSize=9,leading=14,spaceBefore=7,spaceAfter=10,**common),
        'cell':ParagraphStyle('cell',fontSize=9.3,leading=14,**common),
        'head':ParagraphStyle('head',fontSize=9.3,leading=14,textColor=colors.white,fontName=FONT,wordWrap='CJK'),
        'list':ParagraphStyle('list',fontSize=10.2,leading=16,leftIndent=14,firstLineIndent=-12,spaceAfter=7,**common),
    }


def table(block,sty,heading=None):
    head=block['children'][0]['children']
    body=block['children'][1]['children']
    data=[[Paragraph(inline(cell['children']),sty['head']) for cell in head]]
    data.extend([[Paragraph(inline(cell['children']),sty['cell']) for cell in row['children']] for row in body])
    n=len(head)
    weights={2:[2,5],3:[1.2,3,3],4:[1.2,1.3,3.6,3.6],5:[1.6,1.2,1.5,1.5,1.5],
             6:[1.3,1.2,1.2,1.2,1.2,1.5],7:[1,1.5,1.2,1.2,1.2,1.2,1.8],
             8:[.8,1.4,1.2,1.2,1.2,1.4,1.4,1]}[n]
    if '结束情况' in inline(head[-1]['children']):
        weights=[1.1,1,1,1,1.2,1.1,2.7]
    widths=[WIDTH*w/sum(weights) for w in weights]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#31566D')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#F1F5F7'),colors.white]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#31566D')),
        ('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#CED9E1')),
    ]))
    return [KeepTogether(([heading] if heading is not None else [])+[t,Spacer(1,10)])]


def image_flows(node,sty,index,heading=None):
    path=HERE/unquote(node['attrs']['url'])
    caption='图'+str(index)+'  '+inline(node['children'])
    if path.name.startswith('02-'):
        crops=[(.035,.49),(.48,.92)]
        names=['ROS直接通信与本地网关','高质量Wi-Fi与受限Wi-Fi']
        note='空心圆为起点，方块为最后位置。灰色为评价用障碍物；轨迹与路程来自180秒任务窗口，不是规划路径。'
    elif path.name.startswith('04-'):
        crops=[(.025,.337),(.34,.645),(.648,.95)]
        names=['第1轮配对','第2轮配对','第3轮配对']
        note='细线为全窗轨迹，粗线为95%至98%覆盖期间运动；空心圆/方块为起点/最后位置；三角形为目标，红叉为导航失败目标。灰色真值仅供评价，未拟合平移。'
    else:
        crops=None
    if crops:
        source=PILImage.open(path)
        flows=[]
        for i,((top,bottom),name) in enumerate(zip(crops,names),1):
            region=source.crop((0,round(top*source.height),source.width,round(bottom*source.height)))
            dest=TEMP/f'figure-{index}-row-{i}.png'
            region.save(dest)
            height=WIDTH*region.height/region.width
            prefix=[heading] if heading is not None and i==1 else []
            flows.append(KeepTogether(prefix+[Paragraph(caption+f'（{i}/{len(crops)}）：'+name,sty['caption']),
                                      Image(str(dest),width=WIDTH,height=height),Paragraph(note,sty['note'])]))
            if i<len(crops): flows.append(PageBreak())
        return flows
    with PILImage.open(path) as im:
        height=WIDTH*im.height/im.width
    prefix=[heading] if heading is not None else []
    return [KeepTogether(prefix+[Paragraph(caption,sty['caption']),Image(str(path),width=WIDTH,height=height)]),Spacer(1,10)]


def page_header(canvas,doc):
    canvas.saveState()
    canvas.setFont(FONT,8.5)
    canvas.setFillColor(colors.HexColor('#637587'))
    canvas.drawString(38,SIZE[1]-22,'三机器人探索 | ROS直接通信、本地网关与Wi-Fi对比')
    canvas.drawRightString(SIZE[0]-38,20,f'第 {doc.page} 页')
    canvas.setStrokeColor(colors.HexColor('#DDE4E9'))
    canvas.line(38,SIZE[1]-29,SIZE[0]-38,SIZE[1]-29)
    canvas.restoreState()


def main():
    TEMP.mkdir(parents=True,exist_ok=True)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    pdfmetrics.registerFont(TTFont(FONT,'/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',subfontIndex=0))
    pdfmetrics.registerFontFamily(FONT,normal=FONT,bold=FONT,italic=FONT,boldItalic=FONT)
    sty=styles()
    tree=mistune.create_markdown(renderer='ast',plugins=['table'])(SOURCE.read_text())
    story=[];image_index=0
    for block in tree:
        kind=block['type']
        if kind=='heading':
            level=block['attrs']['level']
            story.append(Paragraph(inline(block['children']),sty['title' if level==1 else 'h2' if level==2 else 'h3']))
        elif kind=='paragraph':
            if len(block['children'])==1 and block['children'][0]['type']=='image':
                heading=None
                if story and isinstance(story[-1],Paragraph) and story[-1].style.name in ('h2','h3'):
                    heading=story.pop()
                image_index+=1;story.extend(image_flows(block['children'][0],sty,image_index,heading))
            else:
                story.append(Paragraph(inline(block['children']),sty['body']))
        elif kind=='list':
            for i,item in enumerate(block['children'],1):
                content=''.join(inline(v.get('children',[])) for v in item['children'])
                prefix=str(i)+'. ' if block['attrs']['ordered'] else '• '
                story.append(Paragraph(prefix+content,sty['list']))
        elif kind=='table':
            heading=None
            if story and isinstance(story[-1],Paragraph) and story[-1].style.name in ('h2','h3'):
                heading=story.pop()
            story.extend(table(block,sty,heading))
        elif kind!='blank_line':
            raise ValueError('Unhandled Markdown block: '+kind)
    doc=SimpleDocTemplate(str(OUTPUT),pagesize=SIZE,rightMargin=38,leftMargin=38,
                          topMargin=43,bottomMargin=34,title='通信方式对比图表汇总',author='项目文档')
    doc.build(story,onFirstPage=page_header,onLaterPages=page_header)
    shutil.copy2(OUTPUT,HERE/OUTPUT.name)
    target=Path('/home/zhuyulab/Desktop/通信方式对比图表汇总')/OUTPUT.name
    shutil.copy2(OUTPUT,target)
    print(OUTPUT)
    print(target)
    print('Embedded all 5 figures; tall trajectory figures paginated by their original panel rows.')


if __name__=='__main__':
    main()
