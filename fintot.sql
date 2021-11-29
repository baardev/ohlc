set @tots:= 0;

update orders set fintot = null WHERE session = 'scabbard' ;
UPDATE orders SET runtotnet = credits - fees;
update orders set fintot = (@tots := @tots + runtotnet) WHERE session = 'scabbard' ;

