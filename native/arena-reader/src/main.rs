//! CBA-owned JSON-lines subprocess adapter. Source data is opened read-only by cbvault.
use std::io::{self, BufRead, Write};
use cbvault::bridge::{Database,GameBuf,Generation,Filter,Range,scan};
use cbvault_format::game::RecordKind;
use serde_json::{json,Value};
fn emit(v:Value) { println!("{}",v); let _=io::stdout().flush(); }
fn main(){
 let args:Vec<String>=std::env::args().collect();
 if args.len()!=2 {emit(json!({"error":"Usage: arena-reader <database.cbh>"}));return;}
 let db=match Database::open(&args[1]){Ok(d)=>d,Err(e)=>{emit(json!({"error":e.to_string()}));return;}};
 emit(json!({"ready":true,"records":db.records(),"backend":"cbvault 0.1.7"}));
 let mut buf=GameBuf::new();
 for line in io::stdin().lock().lines(){
  let Ok(line)=line else{break}; let r:Value=match serde_json::from_str(&line){Ok(v)=>v,Err(e)=>{emit(json!({"error":e.to_string(),"end":true}));continue;}};
  let cmd=r["cmd"].as_str().unwrap_or("");
  if cmd=="close"{break;}
  if cmd=="info" {
   let mut games=0u64;let mut texts=0u64;let mut deleted=0u64;let mut other=0u64;
   for id in 1..=db.records(){match db.header_ref(id){Ok(h)=>{if h.is_deleted(){deleted+=1;}else{match h.kind(){RecordKind::Game=>games+=1,RecordKind::Text=>texts+=1,_=>other+=1}}},Err(e)=>{emit(json!({"id":id,"error":e.to_string()}));other+=1;}}}
   emit(json!({"records":db.records(),"games":games,"texts":texts,"deleted":deleted,"other":other,"end":true}));continue;
  }
  if cmd=="search" {
   let name=r["player"].as_str().unwrap_or("");
   if name.chars().count()<3 || db.generation()!=Generation::Classic {emit(json!({"error":"Native player-prefix search requires classic CBH and at least 3 characters","end":true}));continue;}
   let result=(|| -> Result<Value,Box<dyn std::error::Error>> {
    let ids=db.entities().find_players_prefix(name)?;
    if ids.len()>1000{return Err("Player prefix is too broad".into());}
    let mut f=cbvault::bridge::any_player(&ids);
    if let Some(year)=r["year"].as_i64(){f=f.and(Filter::YearBetween(Range::new(year as i32,year as i32)));}
    let hits=scan(&db,&f,2)?;
    Ok(json!({"ids":hits.matches().iter().take(100).map(|m|m.id).collect::<Vec<_>>(),"matches":hits.len(),"records_scanned":hits.stats().records,"end":true}))
   })();
   match result{Ok(v)=>emit(v),Err(e)=>emit(json!({"error":e.to_string(),"end":true}))};continue;
  }
  let start=r["id"].as_u64().unwrap_or(1) as u32;
  let count=if cmd=="game" {1}else{r["count"].as_u64().unwrap_or(100).min(1000000) as u32};
  if start==0 || start>db.records(){emit(json!({"id":start,"error":"Game identifier out of range","end":true}));continue;}
  for id in start..=start.saturating_add(count-1).min(db.records()){
   match db.header_ref(id){
    Ok(h)=>{if h.is_deleted() || !matches!(h.kind(),RecordKind::Game|RecordKind::Analysis){emit(json!({"id":id,"skipped":format!("{:?}",h.kind()),"deleted":h.is_deleted()}));continue;}}
    Err(e)=>{emit(json!({"id":id,"error":e.to_string()}));continue;}
   }
   match db.game_pgn_with(id,&mut buf,true){Ok(pgn)=>match db.game_with(id,&mut buf,false){
    Ok(g)=>emit(json!({"id":id,"pgn":pgn,"native_header":{"White":g.white,"Black":g.black,"Event":g.event,"Site":g.site}})),
    Err(e)=>emit(json!({"id":id,"error":format!("Header comparison read failed: {}",e)}))
   },Err(e)=>emit(json!({"id":id,"error":e.to_string()}))}
  }
  emit(json!({"end":true}));
 }
}
