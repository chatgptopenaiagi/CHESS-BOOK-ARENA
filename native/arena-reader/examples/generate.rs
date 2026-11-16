//! Generated, redistributable fixtures using cbvault's MIT fixture encoder.
use cbvault_fixtures::classic::{self,Builder,Tok};
use gigachess::Board;
fn main(){
 let dest=std::env::args().nth(1).expect("destination");std::fs::create_dir_all(&dest).unwrap();
 let mut b=Builder::new();b.text(&[(0,b"Synthetic non-game record")]);
 let tokens=[Tok::Mv("f2f3"),Tok::Mv("e7e5"),Tok::Mv("g2g4"),Tok::Mv("d8h4"),Tok::End];
 let stream=classic::encode(&Board::startpos(),&tokens,0,false);let record=classic::move_record(0,None,None,&stream);b.game(&record)[0x1b]=0;
 b.annotations(&classic::annotation_items(2,&[classic::text_item(-1,false,0,"Generated fixture comment")]));
 let db=b.write("arena-fixture");
 for p in std::fs::read_dir(db.dir()).unwrap(){let p=p.unwrap().path();std::fs::copy(&p,std::path::Path::new(&dest).join(p.file_name().unwrap())).unwrap();}
}
