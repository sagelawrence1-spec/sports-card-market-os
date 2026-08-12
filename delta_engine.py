import json

def compare_signal(current, previous_row):
    if previous_row is None:
        return {'status':'NEW','signal_change':None,'rar_delta':None,'mi_delta':None,'alert_added':list(current.alerts),'alert_removed':[]}
    # memory.py previous tuple: run_id, signal, confidence, ir, rar, mi, cie, alerts, diagnostics_json
    prev_signal=previous_row[1]; prev_rar=float(previous_row[4] or 0); prev_mi=float(previous_row[5] or 0)
    prev_alerts=set((previous_row[7] or '').split('|')) if previous_row[7] else set()
    cur_alerts=set(current.alerts)
    strength={'STRONG SELL':0,'SELL':1,'TRIM':2,'AVOID':2,'WATCH':3,'HOLD':4,'ACCUMULATE':5,'BUY':6,'STRONG BUY':7}
    if current.signal!=prev_signal:
        if strength.get(current.signal,3)>strength.get(prev_signal,3): status='STRENGTHENED'
        elif strength.get(current.signal,3)<strength.get(prev_signal,3): status='WEAKENED'
        else: status='CHANGED'
    else:
        dr=current.rar_score-prev_rar; dm=current.mi_score-prev_mi
        status='STRENGTHENED' if dr>=5 or dm>=8 else ('WEAKENED' if dr<=-5 or dm<=-8 else 'UNCHANGED')
    return {
      'status':status,'signal_change':f'{prev_signal}->{current.signal}' if prev_signal!=current.signal else None,
      'rar_delta':round(current.rar_score-prev_rar,1),'mi_delta':round(current.mi_score-prev_mi,1),
      'alert_added':sorted(cur_alerts-prev_alerts),'alert_removed':sorted(prev_alerts-cur_alerts)
    }
