package local.ru;

import android.app.Dialog;
import android.app.Activity;
import org.json.JSONObject;
import android.content.*;
import android.content.pm.*;
import android.graphics.*;
import android.graphics.drawable.*;
import android.text.TextUtils;
import android.util.Log;
import android.util.TypedValue;
import android.view.*;
import android.widget.*;
import org.json.JSONArray;
import java.lang.reflect.*;
import java.text.Collator;
import java.util.*;

/** Personal tiles for the stock camping row. No application is removed or disabled. */
public final class CampingApps {
    private static final String PREFIX="local.ru.app:", ADD="local.ru.add", GROUP="local.ru.folder:", PREF="camping_tiles_ru";
    private static final WeakHashMap<View,List<?>> SOURCES=new WeakHashMap<>();
    private static final WeakHashMap<View,String> BOUND=new WeakHashMap<>();
    private static final WeakHashMap<View,int[]> VISIBILITY=new WeakHashMap<>();
    private static final WeakHashMap<View,List<?>> VISIBLE=new WeakHashMap<>();
    private static String moving;
    private static int navigationKey;
    private static Dialog dialog;
    private static boolean suppressConfirmUp;
    private static final WeakHashMap<View,Runnable> PENDING=new WeakHashMap<>();
    private static Object call(Object target,String method) throws Exception {return target.getClass().getMethod(method).invoke(target);}
    private static String name(Object vm) throws Exception {return (String)call(call(vm,"getModel"),"getName");}
    private static SharedPreferences prefs(Context c){return c.getSharedPreferences(PREF,Context.MODE_PRIVATE);}
    private static List<String> saved(Context c,String key){
        List<String> out=new ArrayList<>();
        try {JSONArray a=new JSONArray(prefs(c).getString(key,"[]"));for(int i=0;i<a.length();i++){String s=a.getString(i);if(!out.contains(s))out.add(s);}}
        catch(Exception e){Log.w("CampingApps","Invalid saved list: "+key,e);}
        return out;
    }
    private static void save(Context c,String key,List<String> values){prefs(c).edit().putString(key,new JSONArray(values).toString()).apply();}
    private static String label(Context c,String pkg){try{return c.getPackageManager().getApplicationLabel(c.getPackageManager().getApplicationInfo(pkg,0)).toString();}catch(Exception e){return pkg;}}
    private static Object tile(String key,String title) throws Exception {
        Class<?> model=Class.forName("com.dangbei.leard.leradlauncher.provider.dal.net.http.entity.outdoors.OutDoorsNavItem");
        Class<?> jump=Class.forName("com.dangbei.leradbase.base_data.entity.JumpConfig");
        Object data=model.getConstructor(String.class,String.class,String.class,String.class,jump,String.class).newInstance(key,title,"","",null,"");
        return Class.forName("com.strive.outdoors_home_business.entity.OutDoorsNavItemVm").getConstructor(model).newInstance(data);
    }
    public static List<?> decorate(View row,List<?> nativeItems){
        if(nativeItems==null)return null;
        try {
            List<Object> originals=new ArrayList<>();for(Object vm:nativeItems){String key=name(vm);if(key==null||!key.startsWith("local.ru."))originals.add(vm);}
            SOURCES.put(row,originals);
            Context c=row.getContext();List<Object> result=new ArrayList<>();List<Folder> folders=folders(c);Set<String> grouped=new HashSet<>();for(Folder f:folders)grouped.addAll(f.apps);
            for(String pkg:saved(c,"apps"))if(!grouped.contains(pkg))result.add(tile(PREFIX+pkg,label(c,pkg)));
            for(Folder f:folders)result.add(tile(GROUP+f.id,f.title));
            List<String> hidden=saved(c,"hidden");for(Object vm:originals)if(!hidden.contains(name(vm)))result.add(vm);
            final List<String> order=saved(c,"order");final String sort=prefs(c).getString("sort","manual");final Collator collator=Collator.getInstance(new Locale("ru"));
            result.sort((a,b)->{try{
                String ka=name(a),kb=name(b);
                if(sort.equals("manual")){int ia=order.indexOf(ka),ib=order.indexOf(kb);return Integer.compare(ia<0?Integer.MAX_VALUE:ia,ib<0?Integer.MAX_VALUE:ib);}
                if(sort.equals("apps")||sort.equals("folders")){int pa=kind(ka,sort),pb=kind(kb,sort);if(pa!=pb)return Integer.compare(pa,pb);}
                return collator.compare(title(a),title(b));
            }catch(Exception e){return 0;}});
            result.add(tile(ADD,"Добавить приложение"));VISIBLE.put(row,result);row.post(()->layout(row));return result;
        }catch(Exception e){Log.e("CampingApps","Cannot build tiles",e);return nativeItems;}
    }
    private static int kind(String key,String sort){return sort.equals("folders")?(key.startsWith(GROUP)?0:key.startsWith(PREFIX)?1:2):(key.startsWith(PREFIX)?0:key.startsWith(GROUP)?1:2);}
    private static String title(Object vm)throws Exception{Object value=call(call(vm,"getModel"),"getTitle");String text=value==null?"":value.toString();try{return Class.forName("local.ru.Ui").getMethod("translate",CharSequence.class).invoke(null,text).toString();}catch(Exception ignored){return text;}}
    public static void detached(View row){
        if(dialog!=null)dialog.dismiss();
        SOURCES.remove(row);VISIBLE.remove(row);moving=null;navigationKey=0;
    }
    public static void beforeBind(View view){
        Runnable pending=PENDING.remove(view);if(pending!=null)view.removeCallbacks(pending);
        int[] old=VISIBILITY.remove(view);
        if(old!=null&&view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<Math.min(old.length,group.getChildCount());i++)group.getChildAt(i).setVisibility(old[i]);}
        if(view.getForeground() instanceof TileArt)view.setForeground(null);
        BOUND.remove(view);PRESSES.remove(view);
    }
    public static void afterBind(View view){
        try {
            Object vm=call(view,"getNavItem");String key=name(vm);BOUND.put(view,key);
            view.setOnLongClickListener(v->{menu(v);return true;});
            if(ADD.equals(key)||key.startsWith(PREFIX)||key.startsWith(GROUP)){
                if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;int[] old=new int[group.getChildCount()];for(int i=0;i<old.length;i++){old[i]=group.getChildAt(i).getVisibility();group.getChildAt(i).setVisibility(View.INVISIBLE);}VISIBILITY.put(view,old);}
                String title=ADD.equals(key)?"Добавить приложение":key.startsWith(GROUP)?title(vm):label(view.getContext(),key.substring(PREFIX.length()));
                Drawable icon=null,banner=null;if(key.startsWith(PREFIX)){
                    String pkg=key.substring(PREFIX.length());PackageManager pm=view.getContext().getPackageManager();
                    try{icon=pm.getApplicationIcon(pkg);}catch(Exception ignored){}
                    try{Intent launch=pm.getLeanbackLaunchIntentForPackage(pkg);if(launch!=null){ResolveInfo info=pm.resolveActivity(launch,0);if(info!=null)banner=info.activityInfo.loadBanner(pm);}if(banner==null)banner=pm.getApplicationBanner(pkg);}catch(Exception ignored){}
                }
                view.setForeground(new TileArt(view,title,icon,banner,ADD.equals(key),key.startsWith(GROUP)));view.setContentDescription(title);
            }
            size(view);
        }catch(Exception e){Log.e("CampingApps","Cannot bind tile",e);}
    }
    public static boolean activityKey(Activity activity,KeyEvent event){
        View focus=activity.getCurrentFocus();if(focus==null||!BOUND.containsKey(focus))return false;
        if(moving!=null)return moveKey(focus,event);
        return key(focus,event);
    }
    private static final class Press {boolean held,longPress;}
    private static final WeakHashMap<View,Press> PRESSES=new WeakHashMap<>();
    public static boolean key(View v,KeyEvent event){
        if(!BOUND.containsKey(v))return false;
        interaction(v.getContext(),false);
        if(moving!=null)return moveKey(v,event);
        int code=event.getKeyCode();
        if(verticalKey(v,event))return true;
        if(code==KeyEvent.KEYCODE_MENU){if(event.getAction()==KeyEvent.ACTION_UP)menu(v);return true;}
        if(code!=KeyEvent.KEYCODE_DPAD_CENTER&&code!=KeyEvent.KEYCODE_ENTER&&code!=KeyEvent.KEYCODE_NUMPAD_ENTER)return false;
        Press press=PRESSES.get(v);if(press==null){press=new Press();PRESSES.put(v,press);}final Press state=press;
        if(event.getAction()==KeyEvent.ACTION_DOWN){
            if(event.getRepeatCount()==0){
                state.held=true;state.longPress=false;
                Runnable old=PENDING.remove(v);if(old!=null)v.removeCallbacks(old);
                Runnable pending=()->{PENDING.remove(v);if(state.held&&v.isAttachedToWindow()&&v.hasFocus()){state.longPress=true;suppressConfirmUp=true;menu(v);}};
                PENDING.put(v,pending);v.postDelayed(pending,650);
            }else if(event.isLongPress()&&state.held&&!state.longPress){
                Runnable pending=PENDING.remove(v);if(pending!=null)v.removeCallbacks(pending);
                state.longPress=true;suppressConfirmUp=true;menu(v);
            }
        }else if(event.getAction()==KeyEvent.ACTION_UP){
            Runnable pending=PENDING.remove(v);if(pending!=null)v.removeCallbacks(pending);
            boolean click=state.held&&!state.longPress&&!event.isCanceled();state.held=false;if(click)try{v.getClass().getMethod("onClick",View.class).invoke(v,v);}catch(Exception e){Log.e("CampingApps","Cannot open tile",e);}
        }
        return true;
    }
    // The stock camping handler sends vertical arrows straight to another section.
    // Consume both halves of a key press while moving between rows inside our grid.
    private static boolean verticalKey(View view,KeyEvent event){
        int code=event.getKeyCode();if(code!=KeyEvent.KEYCODE_DPAD_UP&&code!=KeyEvent.KEYCODE_DPAD_DOWN)return false;
        if(event.getAction()==KeyEvent.ACTION_UP){if(navigationKey==code){navigationKey=0;return true;}return false;}
        if(event.getAction()!=KeyEvent.ACTION_DOWN)return false;
        View row=row(view);if(row==null)return false;int rows=prefs(view.getContext()).getInt("rows",1);List<?> items=VISIBLE.get(row);
        if(rows<=1||items==null)return false;
        try {
            int index=-1;for(int i=0;i<items.size();i++)if(Objects.equals(name(items.get(i)),BOUND.get(view))){index=i;break;}
            boolean inside=index>=0&&(code==KeyEvent.KEYCODE_DPAD_UP?index%rows>0:index%rows<rows-1&&index+1<items.size());
            if(!inside)return navigationKey==code;
            navigationKey=code;int target=index+(code==KeyEvent.KEYCODE_DPAD_UP?-1:1);
            row.getClass().getMethod("setSelectedPosition",int.class).invoke(row,target);
            Object manager=call(row,"getLayoutManager");View next=(View)manager.getClass().getMethod("findViewByPosition",int.class).invoke(manager,target);if(next!=null)next.requestFocus();
            return true;
        }catch(Exception e){navigationKey=0;Log.e("CampingApps","Cannot move between rows",e);return false;}
    }
    public static boolean click(View view){
        if(moving!=null||(dialog!=null&&dialog.isShowing()))return true;
        String key=BOUND.get(view);
        if(ADD.equals(key)){picker(view);return true;}
        if(key!=null&&key.startsWith(GROUP)){openFolder(row(view),key.substring(GROUP.length()));return true;}
        if(key==null||!key.startsWith(PREFIX))return false;
        Context c=view.getContext();String pkg=key.substring(PREFIX.length());
        try {Intent intent=c.getPackageManager().getLeanbackLaunchIntentForPackage(pkg);if(intent==null)intent=c.getPackageManager().getLaunchIntentForPackage(pkg);
            if(intent==null)throw new ActivityNotFoundException();intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);c.startActivity(intent);
        }catch(Exception e){Toast.makeText(c,"Приложение недоступно. Ярлык можно убрать через «Меню».",Toast.LENGTH_LONG).show();}
        return true;
    }
    private static View row(View view){View current=view;while(current!=null){if(SOURCES.containsKey(current))return current;ViewParent p=current.getParent();current=p instanceof View?(View)p:null;}return null;}
    private static void refresh(View row,String focus){
        if(row==null)return;
        interaction(row.getContext(),dialog!=null&&dialog.isShowing());
        try {
            List<?> source=SOURCES.get(row);if(source==null)return;
            row.getClass().getMethod("setNavItemList",List.class).invoke(row,new ArrayList<>(source));
            int index=0;List<?> visible=VISIBLE.get(row);
            if(visible!=null)for(int i=0;i<visible.size();i++)if(Objects.equals(name(visible.get(i)),focus)){index=i;break;}
            final int selected=index;
            row.post(()->{try{row.getClass().getMethod("setSelectedPosition",int.class).invoke(row,selected);row.requestFocus();}catch(Exception e){Log.w("CampingApps","Focus refresh",e);}});
        }catch(Exception e){Log.e("CampingApps","Cannot refresh tiles",e);Toast.makeText(row.getContext(),"Не удалось обновить плитки. Откройте «Кемпинг» ещё раз.",Toast.LENGTH_LONG).show();}
    }
    private static final class Choice {
        String title,detail;final Drawable icon;final Runnable action;boolean keepOpen;
        Choice(String title,String detail,Drawable icon,Runnable action){this.title=title;this.detail=detail;this.icon=icon;this.action=action;}
    }
    private static void menu(View view){
        final View row=row(view);if(row==null)return;Context c=view.getContext();String key=BOUND.get(view);List<Choice> choices=new ArrayList<>();
        choices.add(new Choice("Добавить приложение","Выбрать из установленных",null,()->picker(row)));
        if(key!=null&&!ADD.equals(key)){
            choices.add(new Choice("Переместить","Стрелки — выбрать место, OK — сохранить",null,()->{manualOrder(row);moving=key;Toast.makeText(c,"Стрелки — место. OK — готово.",Toast.LENGTH_LONG).show();refresh(row,key);}));
            if(key.startsWith(GROUP)){
                String id=key.substring(GROUP.length());
                choices.add(new Choice("Приложения в папке","Добавить или убрать приложения",null,()->folderApps(row,id)));
                choices.add(new Choice("Переименовать папку","Задать своё название",null,()->nameFolder(row,id)));
                choices.add(new Choice("Убрать папку","Её приложения вернутся на главный экран",null,()->{List<Folder> fs=folders(c);fs.removeIf(f->f.id.equals(id));saveFolders(c,fs);refresh(row,ADD);}));
            }else choices.add(new Choice("Убрать плитку","Приложение останется установленным",null,()->{
                boolean custom=key.startsWith(PREFIX);String field=custom?"apps":"hidden";List<String> values=saved(c,field);
                if(custom)values.remove(key.substring(PREFIX.length()));else if(!values.contains(key))values.add(key);
                save(c,field,values);refresh(row,ADD);
            }));
        }
        choices.add(new Choice("Вид и расположение","Ряд или сетка, размер и расстояния",null,()->appearance(row)));
        choices.add(new Choice("Сортировка","По названию или вручную",null,()->sorting(row)));
        choices.add(new Choice("Создать папку","Собрать приложения в группу",null,()->newFolder(row)));
        choices.add(new Choice("Скрытые плитки","Вернуть штатные плитки на главный экран",null,()->hidden(row)));
        show(c,"Плитки «Кемпинга»","OK — выбрать · Назад — закрыть",choices);
    }
    private static void picker(View anchor){
        final View row=row(anchor);if(row==null)return;Context c=anchor.getContext();PackageManager pm=c.getPackageManager();List<String> pinned=saved(c,"apps");
        Map<String,ApplicationInfo> apps=new HashMap<>();
        for(String category:new String[]{Intent.CATEGORY_LEANBACK_LAUNCHER,Intent.CATEGORY_LAUNCHER})for(ResolveInfo info:pm.queryIntentActivities(new Intent(Intent.ACTION_MAIN).addCategory(category),0)){
            ApplicationInfo app=info.activityInfo.applicationInfo;if(app.enabled&&info.activityInfo.enabled&&!app.packageName.equals(c.getPackageName())&&!pinned.contains(app.packageName))apps.put(app.packageName,app);
        }
        List<ApplicationInfo> sorted=new ArrayList<>(apps.values());Collator collator=Collator.getInstance(new Locale("ru"));sorted.sort((a,b)->collator.compare(label(c,a.packageName),label(c,b.packageName)));
        List<Choice> choices=new ArrayList<>();
        for(ApplicationInfo app:sorted){final String pkg=app.packageName;Drawable icon;try{icon=pm.getApplicationIcon(app);}catch(Exception e){icon=null;}
            choices.add(new Choice(label(c,pkg),"Добавить на главный экран",icon,()->{List<String> values=saved(c,"apps");if(!values.contains(pkg))values.add(pkg);save(c,"apps",values);refresh(row,PREFIX+pkg);}));
        }
        show(c,"Добавить приложение",choices.isEmpty()?"Все доступные приложения уже добавлены":"Выберите приложение и нажмите OK",choices);
    }
    private static void hidden(View row){
        Context c=row.getContext();List<String> hidden=saved(c,"hidden");List<Choice> choices=new ArrayList<>();List<?> source=SOURCES.get(row);
        if(source!=null)for(Object vm:source)try{String key=name(vm);if(hidden.contains(key)){
            Object model=call(vm,"getModel");String title=(String)call(model,"getTitle");title=LauncherLabels.translate(title,new HashMap<String,String>()).toString();
            // The native helper includes all previously translated server labels.
            try{title=Class.forName("local.ru.Ui").getMethod("translate",CharSequence.class).invoke(null,title).toString();}catch(Exception ignored){}
            choices.add(new Choice(title,"Вернуть на главный экран",null,()->{List<String> values=saved(c,"hidden");values.remove(key);save(c,"hidden",values);refresh(row,ADD);}));
        }}catch(Exception e){Log.w("CampingApps","Hidden tile",e);}
        show(c,"Скрытые плитки",choices.isEmpty()?"Скрытых плиток нет":"Выберите плитку, которую хотите вернуть",choices);
    }
    private static List<String> visibleKeys(View row){
        List<String> keys=new ArrayList<>();List<?> items=VISIBLE.get(row);if(items!=null)for(Object vm:items)try{String key=name(vm);if(!ADD.equals(key))keys.add(key);}catch(Exception ignored){}return keys;
    }
    private static void manualOrder(View row){save(row.getContext(),"order",visibleKeys(row));prefs(row.getContext()).edit().putString("sort","manual").apply();}
    private static boolean moveKey(View focus,KeyEvent e){
        int code=e.getKeyCode();View row=row(focus);if(row==null){moving=null;return false;}
        if(code==KeyEvent.KEYCODE_BACK||code==KeyEvent.KEYCODE_DPAD_CENTER||code==KeyEvent.KEYCODE_ENTER){if(e.getAction()==KeyEvent.ACTION_UP){moving=null;Toast.makeText(focus.getContext(),"Порядок сохранён",Toast.LENGTH_SHORT).show();}return true;}
        if(code<19||code>22)return false;
        if(e.getAction()!=KeyEvent.ACTION_DOWN)return true;
        List<String> order=visibleKeys(row);int index=order.indexOf(moving);if(index<0){moving=null;return true;}
        int rows=prefs(focus.getContext()).getInt("rows",1);
        int step=code==21?-rows:code==22?rows:code==19?-1:1;
        if(rows>1&&((code==19&&index%rows==0)||(code==20&&index%rows==rows-1)))return true;
        int target=index+step;if(target<0||target>=order.size())return true;
        Collections.swap(order,index,target);save(focus.getContext(),"order",order);refresh(row,moving);return true;
    }
    private static void sorting(View row){Context c=row.getContext();List<Choice> items=new ArrayList<>();
        String[][] options={{"name","По названию"},{"apps","Приложения сначала"},{"folders","Папки сначала"},{"manual","Ручной порядок"}};
        for(String[] option:options)items.add(new Choice(option[1],option[0].equals(prefs(c).getString("sort","manual"))?"Выбрано":"Применить к плиткам главного экрана",null,()->{prefs(c).edit().putString("sort",option[0]).apply();refresh(row,ADD);}));
        items.add(new Choice("Исходный порядок","Сбросить перестановки; приложения и папки сохранятся",null,()->{prefs(c).edit().putString("sort","manual").remove("order").apply();refresh(row,ADD);}));
        show(c,"Сортировка","Папки и штатные плитки тоже участвуют в сортировке",items);
    }
    private static void appearance(View row){Context c=row.getContext();List<Choice> items=new ArrayList<>();SharedPreferences p=prefs(c);
        items.add(new Choice("Ряд или сетка",p.getInt("rows",1)==1?"Горизонтальный ряд":"Сетка: "+p.getInt("rows",1)+" ряда",null,()->setting(row,"rows","Расположение",new String[]{"Горизонтальный ряд","Сетка в два ряда","Сетка в три ряда"},new int[]{1,2,3})));
        items.add(new Choice("Размер плиток",p.getInt("width",320)==280?"Компактные":p.getInt("width",320)==380?"Крупные":"Обычные",null,()->setting(row,"width","Размер плиток",new String[]{"Компактные","Обычные","Крупные"},new int[]{280,320,380})));
        items.add(new Choice("Расстояние между плитками",p.getInt("gap",40)==20?"Небольшое":p.getInt("gap",40)==40?"Обычное":"Широкое",null,()->setting(row,"gap","Расстояние",new String[]{"Небольшое","Обычное","Широкое"},new int[]{20,40,60})));
        items.add(new Choice("Положение на экране",p.getInt("lift",0)==0?"Внизу":"Выше",null,()->setting(row,"lift","Положение блока",new String[]{"Внизу","Выше"},new int[]{0,120})));
        items.add(new Choice("Боковые отступы",p.getInt("edge",80)==80?"Обычные":"Изменены",null,()->setting(row,"edge","Отступы от краёв",new String[]{"Небольшие","Обычные","Широкие"},new int[]{40,80,140})));
        items.add(new Choice("Вернуть обычный вид","Ряд, обычный размер и отступы; плитки сохранятся",null,()->{p.edit().remove("rows").remove("width").remove("gap").remove("lift").remove("edge").apply();refresh(row,ADD);}));
        show(c,"Вид и расположение","Выберите настройку",items);
    }
    private static void setting(View row,String key,String title,String[] labels,int[] values){Context c=row.getContext();List<Choice> items=new ArrayList<>();for(int i=0;i<labels.length;i++){final int value=values[i];items.add(new Choice(labels[i],"Применить",null,()->{prefs(c).edit().putInt(key,value).apply();refresh(row,ADD);}));}show(c,title,"Изменение сразу видно на главном экране",items);}
    private static void integerCall(View view,String method,int value)throws Exception{view.getClass().getMethod(method,int.class).invoke(view,value);}
    private static final class TextSize {
        final float font;final int width,height,left,top,right,bottom;
        TextSize(TextView view,ViewGroup.MarginLayoutParams lp){font=view.getTextSize();width=lp.width;height=lp.height;left=lp.leftMargin;top=lp.topMargin;right=lp.rightMargin;bottom=lp.bottomMargin;}
    }
    private static final WeakHashMap<TextView,TextSize> TEXT_SIZES=new WeakHashMap<>();
    private static void size(View view){
        ViewGroup.LayoutParams lp=view.getLayoutParams();if(lp==null)return;
        int configured=prefs(view.getContext()).getInt("width",320),width=px(view.getContext(),configured),height=Math.round(width*.5625f);
        if(lp.width!=width||lp.height!=height){lp.width=width;lp.height=height;view.setLayoutParams(lp);}
        if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;float scale=configured/320f;
            for(int i=0;i<group.getChildCount();i++){View child=group.getChildAt(i);if(!(child instanceof TextView)||!(child.getLayoutParams() instanceof ViewGroup.MarginLayoutParams))continue;
                TextView text=(TextView)child;ViewGroup.MarginLayoutParams tp=(ViewGroup.MarginLayoutParams)child.getLayoutParams();TextSize base=TEXT_SIZES.get(text);if(base==null){base=new TextSize(text,tp);TEXT_SIZES.put(text,base);}
                text.setTextSize(TypedValue.COMPLEX_UNIT_PX,base.font*scale);tp.width=base.width<0?base.width:Math.round(base.width*scale);tp.height=base.height<0?base.height:Math.round(base.height*scale);
                tp.setMargins(Math.round(base.left*scale),Math.round(base.top*scale),Math.round(base.right*scale),Math.round(base.bottom*scale));text.setLayoutParams(tp);
            }
        }
    }
    private static void layout(View row){
        if(!row.isAttachedToWindow())return;
        try{Context c=row.getContext();SharedPreferences p=prefs(c);int rows=p.getInt("rows",1),width=p.getInt("width",320),gap=Math.max(p.getInt("gap",40),Math.round(width*.11f));
            integerCall(row,"setNumRows",rows);integerCall(row,"setRowHeight",px(c,width*.5625f));integerCall(row,"setHorizontalSpacing",px(c,gap));integerCall(row,"setVerticalSpacing",px(c,gap));integerCall(row,"setLeftSpace",p.getInt("edge",80));integerCall(row,"setRightSpace",p.getInt("edge",80));
            int height=px(c,rows*width*.5625f+(rows-1)*gap+40);ViewGroup.LayoutParams lp=row.getLayoutParams();if(lp!=null){lp.height=height;row.setLayoutParams(lp);}
            if(row.getParent() instanceof LinearLayout){
                ViewGroup parent=(ViewGroup)row.getParent();parent.setClipChildren(false);parent.setClipToPadding(false);
                int lift=px(c,p.getInt("lift",0)),extra=height-px(c,220)+lift;
                ViewGroup.LayoutParams pp=parent.getLayoutParams();if(pp!=null){pp.height=px(c,248)+extra;parent.setLayoutParams(pp);}parent.setTranslationY(0);
                if(parent.getChildCount()>0&&parent.getChildAt(0) instanceof TextView)parent.getChildAt(0).setTranslationY(0);
                if(parent.getParent() instanceof View){View section=(View)parent.getParent();ViewGroup.LayoutParams sp=section.getLayoutParams();if(sp!=null){sp.height=px(c,420)+extra;section.setLayoutParams(sp);}}
            }
            if(row instanceof ViewGroup){ViewGroup group=(ViewGroup)row;for(int i=0;i<group.getChildCount();i++)size(group.getChildAt(i));}
        }catch(Exception e){Log.e("CampingApps","Cannot apply layout",e);}
    }
    private static final class Folder {String id,title;List<String> apps=new ArrayList<>();Folder(String id,String title){this.id=id;this.title=title;}}
    private static List<Folder> folders(Context c){List<Folder> fs=new ArrayList<>();try{JSONArray a=new JSONArray(prefs(c).getString("folders","[]"));for(int i=0;i<a.length();i++){JSONObject o=a.getJSONObject(i);Folder f=new Folder(o.getString("id"),o.getString("title"));JSONArray apps=o.getJSONArray("apps");for(int j=0;j<apps.length();j++)f.apps.add(apps.getString(j));fs.add(f);}}catch(Exception e){Log.w("CampingApps","Invalid folders",e);}return fs;}
    private static void saveFolders(Context c,List<Folder> fs){JSONArray a=new JSONArray();try{for(Folder f:fs){JSONObject o=new JSONObject();o.put("id",f.id);o.put("title",f.title);o.put("apps",new JSONArray(f.apps));a.put(o);}prefs(c).edit().putString("folders",a.toString()).apply();}catch(Exception e){Log.e("CampingApps","Cannot save folders",e);}}
    private static Folder folder(Context c,String id){for(Folder f:folders(c))if(f.id.equals(id))return f;return null;}
    private static void newFolder(View row){List<Choice> choices=new ArrayList<>();for(String name:new String[]{"Видео","Игры","Музыка","Полезное"})choices.add(new Choice(name,"Создать папку и выбрать приложения",null,()->createFolder(row,name)));choices.add(new Choice("Своё название","Ввести с клавиатуры",null,()->nameFolder(row,null)));show(row.getContext(),"Новая папка","Название можно изменить позже",choices);}
    private static void createFolder(View row,String name){Context c=row.getContext();Folder f=new Folder(UUID.randomUUID().toString(),name);List<Folder> fs=folders(c);fs.add(f);saveFolders(c,fs);refresh(row,GROUP+f.id);folderApps(row,f.id);}
    private static void nameFolder(View row,String id){
        Context c=row.getContext();if(dialog!=null&&dialog.isShowing())dialog.dismiss();final Dialog d=new Dialog(c);dialog=d;d.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout root=new LinearLayout(c);root.setOrientation(1);root.setPadding(px(c,30),px(c,30),px(c,30),px(c,30));root.setBackground(bg(0xff1c2938,px(c,22)));root.addView(text(c,"Название папки",34,Color.WHITE));
        EditText input=new EditText(c);input.setTextColor(Color.WHITE);input.setTextSize(TypedValue.COMPLEX_UNIT_PX,px(c,30));input.setSingleLine(true);input.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);input.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(32)});Folder existing=id==null?null:folder(c,id);if(existing!=null)input.setText(existing.title);root.addView(input,new LinearLayout.LayoutParams(-1,px(c,90)));
        Button saveButton=new Button(c);saveButton.setText("Сохранить");saveButton.setTextColor(Color.WHITE);saveButton.setTextSize(TypedValue.COMPLEX_UNIT_PX,px(c,29));android.graphics.drawable.StateListDrawable buttonBg=new android.graphics.drawable.StateListDrawable();buttonBg.addState(new int[]{android.R.attr.state_focused},bg(0xff247f96,px(c,12)));buttonBg.addState(new int[]{},bg(0xff304459,px(c,12)));saveButton.setBackground(buttonBg);root.addView(saveButton,new LinearLayout.LayoutParams(-1,px(c,70)));saveButton.setOnClickListener(v->{String name=input.getText().toString().trim();if(name.isEmpty()){input.setError("Введите название");return;}d.dismiss();if(id==null)createFolder(row,name);else{List<Folder> fs=folders(c);for(Folder f:fs)if(f.id.equals(id))f.title=name;saveFolders(c,fs);refresh(row,GROUP+id);}});
        d.setContentView(root);d.setOnDismissListener(ignored->{if(dialog==d)dialog=null;interaction(c,false);});d.getWindow().setBackgroundDrawableResource(android.R.color.transparent);d.show();interaction(c,true);d.getWindow().setLayout(px(c,800),-2);input.requestFocus();
    }
    private static List<String> launchable(Context c){Set<String> pkgs=new HashSet<>();PackageManager pm=c.getPackageManager();for(String category:new String[]{Intent.CATEGORY_LEANBACK_LAUNCHER,Intent.CATEGORY_LAUNCHER})for(ResolveInfo info:pm.queryIntentActivities(new Intent(Intent.ACTION_MAIN).addCategory(category),0)){ApplicationInfo app=info.activityInfo.applicationInfo;if(app.enabled&&info.activityInfo.enabled&&!app.packageName.equals(c.getPackageName()))pkgs.add(app.packageName);}List<String> list=new ArrayList<>(pkgs);Collator collator=Collator.getInstance(new Locale("ru"));list.sort((a,b)->collator.compare(label(c,a),label(c,b)));return list;}
    private static void folderApps(View row,String id){Context c=row.getContext();Folder f=folder(c,id);if(f==null)return;List<Choice> choices=new ArrayList<>();for(String pkg:launchable(c)){
        Drawable icon=null;try{icon=c.getPackageManager().getApplicationIcon(pkg);}catch(Exception ignored){}final int index=choices.size();
        Choice choice=new Choice((f.apps.contains(pkg)?"✓  ":"")+label(c,pkg),f.apps.contains(pkg)?"В папке":"Добавить в папку",icon,()->{
            List<Folder> fs=folders(c);Folder target=null;for(Folder g:fs)if(g.id.equals(id))target=g;if(target==null)return;boolean remove=target.apps.contains(pkg);
            for(Folder g:fs)g.apps.remove(pkg);if(!remove)target.apps.add(pkg);
            List<String> apps=saved(c,"apps");if(!apps.contains(pkg))apps.add(pkg);save(c,"apps",apps);saveFolders(c,fs);
            Choice item=choices.get(index);item.title=(remove?"":"✓  ")+label(c,pkg);item.detail=remove?"На главном экране":"В папке";refresh(row,GROUP+id);
        });choice.keepOpen=true;choices.add(choice);
    }show(c,f.title,"OK — добавить или убрать · Назад — закончить",choices);}
    private static void openFolder(View row,String id){if(row==null)return;Context c=row.getContext();Folder f=folder(c,id);if(f==null)return;List<Choice> choices=new ArrayList<>();for(String pkg:f.apps){Drawable icon=null;try{icon=c.getPackageManager().getApplicationIcon(pkg);}catch(Exception ignored){}choices.add(new Choice(label(c,pkg),"Открыть",icon,()->{try{Intent intent=c.getPackageManager().getLeanbackLaunchIntentForPackage(pkg);if(intent==null)intent=c.getPackageManager().getLaunchIntentForPackage(pkg);if(intent==null)throw new ActivityNotFoundException();c.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}catch(Exception e){Toast.makeText(c,"Приложение недоступно",Toast.LENGTH_SHORT).show();}}));}choices.add(new Choice("Изменить состав папки","Выбрать приложения",null,()->folderApps(row,id)));show(c,f.title,"OK — открыть · Назад — закрыть",choices);}
    private static int px(Context c,float value){return Math.round(value*c.getResources().getDisplayMetrics().widthPixels/1920f);}
    private static TextView text(Context c,String value,float size,int color){TextView t=new TextView(c);t.setText(value);t.setTextColor(color);t.setTextSize(TypedValue.COMPLEX_UNIT_PX,px(c,size));t.setFontFeatureSettings("kern");return t;}
    private static GradientDrawable bg(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(radius);return d;}
    private static void interaction(Context context,boolean editing){
        try {
            while(context instanceof ContextWrapper && !(context instanceof Activity))context=((ContextWrapper)context).getBaseContext();
            Object owner=context.getClass().getField("C0").get(context);Object fragment=call(owner,"a");
            if(fragment==null||!fragment.getClass().getName().equals("com.strive.outdoors_home_business.OutDoorsHomeFragment"))return;
            if(Boolean.TRUE.equals(call(fragment,"V6")))call(fragment,"n7");
            call(fragment,"o7");
            if(editing)((android.os.Handler)fragment.getClass().getField("m1").get(fragment)).removeMessages(101);
        }catch(Exception e){Log.w("CampingApps","Cannot update camping idle timer",e);}
    }
    private static void show(Context c,String title,String hint,List<Choice> choices){
        if(dialog!=null&&dialog.isShowing())dialog.dismiss();
        final Dialog d=new Dialog(c);dialog=d;d.requestWindowFeature(Window.FEATURE_NO_TITLE);
        d.setOnKeyListener((ignored,code,event)->{
            if(!suppressConfirmUp||(code!=KeyEvent.KEYCODE_DPAD_CENTER&&code!=KeyEvent.KEYCODE_ENTER&&code!=KeyEvent.KEYCODE_NUMPAD_ENTER))return false;
            if(event.getAction()==KeyEvent.ACTION_UP){suppressConfirmUp=false;return true;}
            if(event.getRepeatCount()==0){suppressConfirmUp=false;return false;}return true;
        });
        LinearLayout root=new LinearLayout(c);root.setOrientation(LinearLayout.VERTICAL);int pad=px(c,30);root.setPadding(pad,pad,pad,pad);root.setBackground(bg(0xff1c2938,px(c,22)));
        TextView heading=text(c,title,36,Color.WHITE);heading.setTypeface(Typeface.create("sans-serif-medium",0));root.addView(heading);
        TextView help=text(c,hint,24,0xffbdcad8);help.setPadding(0,px(c,12),0,px(c,22));root.addView(help);
        ListView list=new ListView(c);list.setDivider(null);list.setCacheColorHint(Color.TRANSPARENT);list.setSelector(bg(0xff247f96,px(c,12)));list.setDrawSelectorOnTop(false);
        list.setAdapter(new BaseAdapter(){
            public int getCount(){return choices.size();}public Object getItem(int i){return choices.get(i);}public long getItemId(int i){return i;}
            public View getView(int i,View convert,ViewGroup parent){Choice choice=choices.get(i);LinearLayout line=new LinearLayout(c);line.setGravity(Gravity.CENTER_VERTICAL);line.setPadding(px(c,18),px(c,12),px(c,18),px(c,12));line.setLayoutParams(new AbsListView.LayoutParams(-1,px(c,94)));
                if(choice.icon!=null){ImageView icon=new ImageView(c);icon.setImageDrawable(choice.icon);LinearLayout.LayoutParams ip=new LinearLayout.LayoutParams(px(c,58),px(c,58));ip.rightMargin=px(c,22);line.addView(icon,ip);}
                LinearLayout labels=new LinearLayout(c);labels.setOrientation(1);TextView name=text(c,choice.title,29,Color.WHITE);name.setSingleLine(true);name.setEllipsize(TextUtils.TruncateAt.END);labels.addView(name);TextView sub=text(c,choice.detail,21,0xffbdcad8);sub.setSingleLine(true);labels.addView(sub);line.addView(labels,new LinearLayout.LayoutParams(0,-2,1));return line;
            }
        });
        int count=Math.max(1,Math.min(6,choices.size()));root.addView(list,new LinearLayout.LayoutParams(-1,px(c,94*count)));
        d.setContentView(root);d.setOnDismissListener(ignored->{if(dialog==d)dialog=null;interaction(c,false);});
        list.setOnItemClickListener((parent,v,index,id)->{Choice choice=choices.get(index);if(!choice.keepOpen)d.dismiss();choice.action.run();if(choice.keepOpen)((BaseAdapter)list.getAdapter()).notifyDataSetChanged();});
        Window w=d.getWindow();if(w!=null){w.setBackgroundDrawableResource(android.R.color.transparent);w.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);WindowManager.LayoutParams lp=w.getAttributes();lp.dimAmount=.62f;w.setAttributes(lp);}
        d.show();interaction(c,true);if(w!=null)w.setLayout(px(c,960),-2);list.requestFocus();if(!choices.isEmpty())list.setSelection(0);
    }
    public static void themeBadge(ImageView view){
        final Context context=view.getContext();view.setContentDescription("Выбрано");
        view.setImageDrawable(new Drawable(){
            final Paint paint=new Paint(3);
            public void draw(Canvas canvas){Rect r=getBounds();float scale=r.height()/40f;paint.setColor(0xc91c2938);canvas.drawRoundRect(new RectF(r),8*scale,8*scale,paint);paint.setColor(Color.WHITE);paint.setTypeface(Typeface.create("sans-serif-medium",0));paint.setTextSize(22*scale);paint.setTextAlign(Paint.Align.CENTER);canvas.drawText("✓ Выбрано",r.exactCenterX(),r.exactCenterY()-(paint.ascent()+paint.descent())/2,paint);}
            public int getIntrinsicWidth(){return px(context,140);}public int getIntrinsicHeight(){return px(context,40);}
            public void setAlpha(int a){paint.setAlpha(a);}public void setColorFilter(ColorFilter f){paint.setColorFilter(f);}public int getOpacity(){return PixelFormat.TRANSLUCENT;}
        });
    }
    private static final class TileArt extends Drawable {
        final View owner;final String title;final Drawable icon,banner;final boolean add,folder;final Paint p=new Paint(3);final int appColor;
        TileArt(View owner,String title,Drawable icon,Drawable banner,boolean add,boolean folder){this.owner=owner;this.title=title;this.icon=icon;this.banner=banner;this.add=add;this.folder=folder;this.appColor=iconColor(icon);}
        private static int iconColor(Drawable icon){
            if(icon==null)return 0xff33466a;
            Rect old=new Rect(icon.getBounds());Bitmap bitmap=Bitmap.createBitmap(24,24,Bitmap.Config.ARGB_8888);
            try{icon.setBounds(0,0,24,24);icon.draw(new Canvas(bitmap));long red=0,green=0,blue=0,weight=0;for(int y=0;y<24;y++)for(int x=0;x<24;x++){int color=bitmap.getPixel(x,y),a=Color.alpha(color);red+=Color.red(color)*a;green+=Color.green(color)*a;blue+=Color.blue(color)*a;weight+=a;}if(weight>0)return Color.rgb((int)(red/weight*.55),(int)(green/weight*.55),(int)(blue/weight*.55));return 0xff33466a;}catch(Exception ignored){return 0xff33466a;}finally{icon.setBounds(old);bitmap.recycle();}
        }
        private void focus(Canvas canvas,Rect r,float s,float corner){if(owner.hasFocus()){p.setShader(null);p.setColor(0xff71d8e9);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(3*s);canvas.drawRoundRect(new RectF(r.left+2*s,r.top+2*s,r.right-2*s,r.bottom-2*s),corner,corner,p);p.setStyle(Paint.Style.FILL);}}
        public void draw(Canvas canvas){Rect r=getBounds();float s=r.width()/320f;float corner=20*s;
            if(!add&&!folder){
                int save=canvas.save();Path clip=new Path();clip.addRoundRect(new RectF(r),corner,corner,Path.Direction.CW);canvas.clipPath(clip);
                p.setShader(new LinearGradient(r.left,r.top,r.right,r.bottom,appColor,0xff111b29,Shader.TileMode.CLAMP));canvas.drawRect(r,p);p.setShader(null);
                if(banner!=null&&banner.getIntrinsicWidth()>0&&banner.getIntrinsicHeight()>0){
                    float scale=Math.max(r.width()/(float)banner.getIntrinsicWidth(),r.height()/(float)banner.getIntrinsicHeight());int w=Math.round(banner.getIntrinsicWidth()*scale),h=Math.round(banner.getIntrinsicHeight()*scale);int x=Math.round(r.exactCenterX()-w/2f),y=Math.round(r.exactCenterY()-h/2f);banner.setBounds(x,y,x+w,y+h);banner.draw(canvas);
                }else{
                    if(icon!=null){float size=Math.min(r.height()*.72f,r.width()*.56f);int x=Math.round(r.exactCenterX()-size/2),y=Math.round(r.top+r.height()*.05f);icon.setBounds(x,y,x+Math.round(size),y+Math.round(size));icon.draw(canvas);}
                    p.setShader(new LinearGradient(0,r.top+r.height()*.62f,0,r.bottom,0x00111b29,0xe6111b29,Shader.TileMode.CLAMP));canvas.drawRect(r,p);p.setShader(null);p.setTypeface(Typeface.create("sans-serif-medium",0));p.setTextSize(25*s);p.setColor(Color.WHITE);String caption=title;float width=r.width()-32*s;if(p.measureText(caption)>width){int n=p.breakText(caption,true,width-p.measureText("…"),null);caption=caption.substring(0,n).trim()+"…";}canvas.drawText(caption,r.exactCenterX()-p.measureText(caption)/2,r.bottom-15*s,p);
                }
                canvas.restoreToCount(save);focus(canvas,r,s,corner);return;
            }
            p.setShader(new LinearGradient(r.left,r.top,r.right,r.bottom,add?0xff355363:0xff33466a,add?0xff243946:0xff263247,Shader.TileMode.CLAMP));canvas.drawRoundRect(new RectF(r),corner,corner,p);p.setShader(null);
            if(owner.hasFocus()){p.setColor(0xff71d8e9);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(3*s);canvas.drawRoundRect(new RectF(r.left+2*s,r.top+2*s,r.right-2*s,r.bottom-2*s),corner,corner,p);p.setStyle(Paint.Style.FILL);}
            if(icon!=null){icon.setBounds(r.left+(int)(22*s),r.top+(int)(18*s),r.left+(int)(86*s),r.top+(int)(82*s));icon.draw(canvas);}
            else if(folder){p.setColor(0xffe4c57f);canvas.drawRoundRect(new RectF(r.left+22*s,r.top+25*s,r.left+90*s,r.top+80*s),7*s,7*s,p);canvas.drawRoundRect(new RectF(r.left+22*s,r.top+17*s,r.left+55*s,r.top+42*s),5*s,5*s,p);}
            else {p.setColor(0xffc5e8f0);p.setStrokeWidth(4*s);float x=r.left+52*s,y=r.top+50*s;canvas.drawLine(x-18*s,y,x+18*s,y,p);canvas.drawLine(x,y-18*s,x,y+18*s,p);}
            p.setTypeface(Typeface.create("sans-serif-medium",0));p.setTextSize(28*s);p.setColor(Color.WHITE);
            String first=title,second="";float width=r.width()-44*s;
            if(p.measureText(first)>width){int cut=p.breakText(first,true,width,null);int space=first.lastIndexOf(' ',cut);if(space>0)cut=space;second=first.substring(cut).trim();first=first.substring(0,cut).trim();}
            canvas.drawText(first,r.left+22*s,r.top+119*s,p);
            if(!second.isEmpty()){while(second.length()>1&&p.measureText(second)>width)second=second.substring(0,second.length()-2)+"…";canvas.drawText(second,r.left+22*s,r.top+152*s,p);}
            else if(add||folder){p.setTextSize(21*s);p.setColor(0xffadbdcf);canvas.drawText(add?"Выбрать из списка":"Открыть папку",r.left+22*s,r.top+153*s,p);}
        }
        public void setAlpha(int a){p.setAlpha(a);}public void setColorFilter(ColorFilter f){p.setColorFilter(f);}public int getOpacity(){return PixelFormat.TRANSLUCENT;}
    }
}
