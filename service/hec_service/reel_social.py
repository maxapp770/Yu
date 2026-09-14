"""Account-scoped Reels reactions and comments, encrypted at rest."""
import secrets,re,hashlib
from .core import fail,utc,text
class ReelSocial:
    def reel_social(self,op,a,session):
        rid=a.get('reel_id','');manager=op.startswith('admin.')
        if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',rid):fail(422,'معرّف فيديو غير صالح.')
        who=None
        if manager:
            _,who=self.admin(session)
            if not any(r['id']==rid for r in self.table('videos')):fail(404,'الفيديو غير موجود.')
            cfg=self.reel_config(self.reel_snapshot(True))
        else:
            feed=self.reels_feed();cfg=feed['settings']
            if not any(r['id']==rid for r in feed['rows']):fail(404,'الفيديو غير منشور أو انتهت فترته.')
            if session and session.get('kind')=='customer':who=self.customer_account(session,False)
        user=who['user'] if who else '';name=text(who.get('name',user),100) if who else ''
        write=op not in ('reels.social','admin.reels.comments')
        if write and not user:fail(401,'سجّل الدخول بحساب العميل للتفاعل.')
        if op=='reels.react' and (cfg.get('enableLikes') is False or type(a.get('liked'))!=bool):fail(422,'الإعجاب متوقف أو قيمته غير صالحة.')
        if op=='reels.comment' and cfg.get('enableComments') is False:fail(403,'التعليقات متوقفة.')
        if write:self.store.throttle('reel-social:'+user,30,60)
        key='reel-social:'+str(self.store.get('channel')['epoch'])+':'+hashlib.sha256(rid.encode()).hexdigest()
        with self.store.tx() as db:
            saved=self.store.get(key,db=db);value=self.store.open(saved) if saved else {'likes':[],'comments':[]}
            if op=='reels.react':
                if a['liked'] and user not in value['likes']:value['likes'].append(user)
                if not a['liked'] and user in value['likes']:value['likes'].remove(user)
            elif op=='reels.comment':
                comment=a.get('text');request=a.get('request_id')
                if not isinstance(comment,str) or not 1<=len(comment.strip())<=1000 or not isinstance(request,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',request):fail(422,'نص التعليق أو معرّفه غير صالح.')
                if not any(c['user']==user and c['request']==request for c in value['comments']):
                    if len(value['comments'])>=500:fail(422,'وصل الفيديو إلى حد التعليقات.')
                    value['comments'].append(dict(id=secrets.token_hex(16),user=user,name=name,text=text(comment.strip(),1000),createdAt=utc(),request=request))
            elif op in ('reels.comment.delete','admin.reels.comment.delete'):
                old=next((c for c in value['comments'] if c['id']==a.get('comment_id')),None)
                if not old or not manager and old['user']!=user:fail(403,'لا تملك حذف هذا التعليق.')
                value['comments'].remove(old)
            if write:self.store.put(key,self.store.seal(value),db)
        return dict(likes=len(value['likes']),liked=user in value['likes'],commentCount=len(value['comments']),comments=[{k:c[k] for k in ('id','name','text','createdAt')}|dict(canDelete=manager or c['user']==user) for c in value['comments'][-50:][::-1]],commentsEnabled=cfg.get('enableComments') is not False,canInteract=bool(user))
