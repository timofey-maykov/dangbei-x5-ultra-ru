package local.ru;

import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.view.View;
import android.widget.ImageView;
import android.widget.TextView;
import java.util.HashMap;
import java.util.Map;

/** Local UI labels. Film artwork and server content are left intact. */
public final class LauncherLabels {
    private static final Map<String,String> LABELS = new HashMap<>();
    static {
        String[][] pairs = {
            {"浪漫篝火","У костра"},{"春日樱花","Цветущая сакура"},{"幽静森林","Тихий лес"},{"梦幻极光","Северное сияние"},{"启用中","Выбрано"},{"推荐节目","Для вас"},{"热门推荐","Популярное"},{"为你推荐","Для вас"},{"教育","Обучение"},{"体育","Спорт"},{"纪录片","Документальные"},{"电影","Фильмы"},{"电视剧","Сериалы"},{"剧集","Сериалы"},{"动漫","Аниме"},
            {"短剧","Мини-сериалы"},{"单点","Прокат"},{"芒果TV","Mango TV"},{"综艺","Шоу"},
            {"全部观看记录","История просмотра"},{"最近观看","Недавнее"},{"儿童应用","Приложения"},
            {"动画明星","Герои"},{"讲故事","Сказки"},{"学知识","Учимся"},
            {"看动画","Мультфильмы"},{"听儿歌","Детские песни"},{"做游戏","Игры"},
            {"最近热播","Сериалы\nна ТВ"},{"精选电影","Фильмы"},{"军旅谍战","Военные\nи шпионы"},{"卫视同步","Сериалы\nна ТВ"},
            {"免费剧集","Бесплатные\nсериалы"},{"戏曲","Китайская\nопера"},
            {"免费","Бесплатно"},{"VIP·影视","VIP"},{"单片付费","Платно"},
            {"长辈模式","Крупно"},{"大字模式","Крупно"},{"Крупные значки","Крупно"},{"Крупный интерфейс","Крупно"},
            {"抱歉，跳转出现错误，请稍后再试","Не удалось открыть. Попробуйте ещё раз"},
            {"标准模式","Стандарт"},{"儿童模式","Дети"},{"露营模式","Кемпинг"}
        };
        for(String[] p:pairs) LABELS.put(p[0],p[1]);
    }
    public static CharSequence translate(CharSequence source, Map<String,String> original) {
        if(source==null) return null;
        String s=source.toString();
        String key=s.replace("「","").replace("」","").replace("『","").replace("』","").trim();
        String value=LABELS.get(key);
        if(value==null) value=original.get(key);
        if(value!=null) return value;
        String out=s.replaceAll("已看\\s*(\\d+)%", "$1%")
            .replaceAll("第\\s*(\\d+)\\s*集", "серия $1")
            .replaceAll("(\\d+)集全", "Все серии: $1")
            .replaceAll("更新至(\\d+)集", "До $1 серии")
            .replaceAll("(\\d{1,2})月(\\d{1,2})日", "$2.$1");
        String[][] weather={{"多云","Облачно"},{"晴","Ясно"},{"阴","Пасмурно"},{"小雨","Небольшой дождь"},{"中雨","Дождь"},{"大雨","Сильный дождь"},{"雷阵雨","Гроза"},{"阵雨","Ливень"},{"小雪","Небольшой снег"},{"中雪","Снег"},{"大雪","Снегопад"},{"雾","Туман"}};
        for(String[] p:weather) if(out.matches(java.util.regex.Pattern.quote(p[0])+"\\s*-?\\d+.*") || out.equals(p[0])) {out=p[1]+out.substring(p[0].length()); break;}
        return out.equals(s)?source:out;
    }
    public static void style(TextView view, CharSequence text) {
        String id="";
        try {id=view.getResources().getResourceEntryName(view.getId());} catch(Exception ignored){}
        if(id.equals("view_secondary_recommend_title_tv")) view.setTextColor(0xffe5eaf1);
        if(id.equals("elder_home_my_app_item_name_tv") && "Все приложения".contentEquals(text==null?"":text)) {
            view.setTypeface(Typeface.create("sans-serif",0)); view.setSingleLine(false); view.setMaxLines(2); view.setText("Все\nпрограммы");
        }
    }
    public static boolean child(View owner, ImageView image) {
        String text; int color;
        if(owner.getId()==0x7f09028d) {text="Недавнее"; color=0xff227d65;}
        else if(owner.getId()==0x7f090284) {text="Приложения"; color=0xffa34570;}
        else return false;
        image.setImageDrawable(new LabelDrawable(text,color,36,385));
        owner.setContentDescription(text);
        return true;
    }
    public static boolean elder(View owner, ImageView image, Object model) {
        String text=null;
        for(String getter:new String[]{"getTitle","getMenuName","getNavName"}) {
            try {Object value=model.getClass().getMethod(getter).invoke(model); if(value!=null) {text=LABELS.get(value.toString().trim());}}catch(Exception ignored){}
            if(text!=null) break;
        }
        if(text==null) return false;
        image.setImageDrawable(new LabelDrawable(text,0xff3d4968,32,260));
        owner.setContentDescription(text.replace('\n',' '));
        return true;
    }
    public static void historyBackground(View view) { view.setBackground(new HistoryLabel()); }
    private static final class HistoryLabel extends Drawable {
        final Paint p=new Paint(3);
        @Override public void draw(Canvas c) {
            Rect r=getBounds(); boolean vertical=r.height()>r.width();
            float scale=vertical?r.width()/108f:r.width()/410f;
            p.setShader(new LinearGradient(r.left,r.top,r.right,r.bottom,0xff28a0df,0xff18bdbe,Shader.TileMode.CLAMP));
            Path outline=new Path();float radius=20*scale;
            outline.addRoundRect(new RectF(r),new float[]{0,0,0,0,radius,radius,radius,radius},Path.Direction.CW);
            c.drawPath(outline,p);p.setShader(null);
            p.setColor(Color.WHITE);p.setTypeface(Typeface.create("sans-serif",0));p.setTextSize((vertical?23:26)*scale);
            p.setTextAlign(vertical?Paint.Align.CENTER:Paint.Align.LEFT);
            if(vertical) {
                float x=r.exactCenterX(), y=r.top+95*scale;
                p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(3*scale);c.drawCircle(x,y,24*scale,p);
                c.drawLine(x,y,x,y-15*scale,p);c.drawLine(x,y,x+12*scale,y+6*scale,p);p.setStyle(Paint.Style.FILL);
                c.drawText("История",x,r.top+190*scale,p);
            } else {
                float y=r.exactCenterY()-(p.ascent()+p.descent())/2;
                c.drawText("История просмотра",r.left+20*scale,y,p);
                p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(3*scale);
                Path arrow=new Path();float x=r.right-28*scale;y=r.exactCenterY();
                arrow.moveTo(x-6*scale,y-8*scale);arrow.lineTo(x+2*scale,y);arrow.lineTo(x-6*scale,y+8*scale);c.drawPath(arrow,p);p.setStyle(Paint.Style.FILL);
            }
        }
        @Override public void setAlpha(int a){p.setAlpha(a);}
        @Override public void setColorFilter(ColorFilter f){p.setColorFilter(f);}
        @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
    }
    public static void castBackground(View view) { view.setBackground(new CastBackground()); }
    private static final class CastBackground extends Drawable {
        final Paint p=new Paint(3);
        @Override public void draw(Canvas canvas) {
            Rect r=getBounds(); float x=r.width()/320f,y=r.height()/260f;
            p.setColor(0xffd3dcec); canvas.drawRoundRect(new RectF(r.left,r.top,r.right,r.bottom-18*y),20*x,20*y,p);
            Path tip=new Path(); tip.moveTo(r.centerX()-18*x,r.bottom-20*y); tip.lineTo(r.centerX(),r.bottom); tip.lineTo(r.centerX()+18*x,r.bottom-20*y); tip.close(); canvas.drawPath(tip,p);
            p.setColor(0xff626e7c);p.setTypeface(Typeface.create("sans-serif",0));p.setTextSize(26*y);p.setTextAlign(Paint.Align.CENTER);
            canvas.drawText("Имя проектора",r.exactCenterX(),r.top+48*y,p);
            canvas.drawText("Сеть",r.exactCenterX(),r.top+170*y,p);
            p.setColor(0xffb9c3d3);canvas.drawLine(r.left+20*x,r.top+125*y,r.right-20*x,r.top+125*y,p);
        }
        @Override public void setAlpha(int a){p.setAlpha(a);}
        @Override public void setColorFilter(ColorFilter f){p.setColorFilter(f);}
        @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
    }
    private static final class LabelDrawable extends Drawable {
        final String text; final int background; final float size; final int width; final Paint paint=new Paint(3);
        LabelDrawable(String text,int background,float size,int width){this.text=text;this.background=background;this.size=size;this.width=width;}
        @Override public void draw(Canvas canvas) {
            Rect r=getBounds(); float scale=r.height()/120f;
            paint.setColor(background); canvas.drawRoundRect(new RectF(r),20*scale,20*scale,paint);
            paint.setColor(Color.WHITE); paint.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
            paint.setTextAlign(Paint.Align.CENTER); paint.setTextSize(size*scale);
            String[] lines=text.split("\n"); float line=paint.getFontSpacing();
            float y=r.exactCenterY()-(paint.ascent()+paint.descent())/2-(lines.length-1)*line/2;
            for(String s:lines){canvas.drawText(s,r.exactCenterX(),y,paint); y+=line;}
        }
        @Override public void setAlpha(int alpha){paint.setAlpha(alpha);}
        @Override public void setColorFilter(ColorFilter filter){paint.setColorFilter(filter);}
        @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
        @Override public int getIntrinsicWidth(){return width;}
        @Override public int getIntrinsicHeight(){return 120;}
    }
}
