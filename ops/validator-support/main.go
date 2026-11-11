// Standalone administrative service. Deliberately outside sobya/app and the
// consensus runtime. It has no chain transaction signer or write-RPC client.
package main

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

type Application struct {
	ID string `json:"id"`
	OperatorName string `json:"operator_name"`
	Contact string `json:"contact"`
	AccountAddress string `json:"account_address"`
	ValidatorAddress string `json:"validator_address"`
	ConsensusPubKey string `json:"consensus_pubkey"`
	NodeEndpoint string `json:"node_endpoint"`
	SoftwareVersion string `json:"software_version"`
	Commission string `json:"commission"`
	Status string `json:"status"`
	RequestedAmount string `json:"requested_amount,omitempty"`
	ApprovedAmount string `json:"approved_amount,omitempty"`
	Notes string `json:"notes,omitempty"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
	Evidence []Evidence `json:"evidence,omitempty"`
	Tranches []Tranche `json:"tranches,omitempty"`
}
type Evidence struct {
	ObservedAt time.Time `json:"observed_at"`
	Source string `json:"source"`
	Height int64 `json:"height,omitempty"`
	SignedBlocks int64 `json:"signed_blocks,omitempty"`
	WindowBlocks int64 `json:"window_blocks,omitempty"`
	Bonded bool `json:"bonded"`
	Jailed bool `json:"jailed"`
	Notes string `json:"notes,omitempty"`
}
type Tranche struct {
	Amount string `json:"amount"`
	TxHash string `json:"tx_hash,omitempty"`
	Status string `json:"status"`
	RecordedAt time.Time `json:"recorded_at"`
}
type Store struct {
	mu sync.Mutex
	path string
	apps map[string]Application
}
func newID() (string,error) { b:=make([]byte,16); if _,e:=rand.Read(b); e!=nil{return "",e}; return hex.EncodeToString(b),nil }
func NewStore(path string) (*Store,error) {
	s:=&Store{path:path,apps:map[string]Application{}}
	b,e:=os.ReadFile(path); if e==nil { if e=json.Unmarshal(b,&s.apps); e!=nil{return nil,fmt.Errorf("decode store: %w",e)} } else if !errors.Is(e,os.ErrNotExist) { return nil,e }
	return s,nil
}
func (s *Store) saveLocked() error {
	b,e:=json.MarshalIndent(s.apps,"","  "); if e!=nil{return e}
	if e=os.MkdirAll(filepath.Dir(s.path),0700); e!=nil{return e}
	tmp:=s.path+".tmp"
	if e=os.WriteFile(tmp,b,0600); e!=nil{return e}
	if e=os.Rename(tmp,s.path); e!=nil{_ = os.Remove(tmp); return e}
	return nil
}
func (s *Store) create(a Application) (Application,error) {
	s.mu.Lock(); defer s.mu.Unlock()
	for _,old:=range s.apps { if old.AccountAddress==a.AccountAddress { return Application{},errors.New("an application already exists for this account") } }
	id,e:=newID(); if e!=nil{return Application{},e}
	now:=time.Now().UTC(); a.ID=id; a.Status="submitted"; a.CreatedAt=now; a.UpdatedAt=now
	s.apps[id]=a
	if e=s.saveLocked(); e!=nil{delete(s.apps,id);return Application{},e}
	return a,nil
}
func (s *Store) list() []Application {
	s.mu.Lock(); defer s.mu.Unlock()
	out:=make([]Application,0,len(s.apps)); for _,a:=range s.apps {out=append(out,a)}; return out
}
func (s *Store) mutate(id string, fn func(*Application) error) (Application,error) {
	s.mu.Lock(); defer s.mu.Unlock()
	a,ok:=s.apps[id]; if !ok{return Application{},errors.New("application not found")}
	old:=a
	if e:=fn(&a); e!=nil{return Application{},e}
	a.UpdatedAt=time.Now().UTC(); s.apps[id]=a
	if e:=s.saveLocked(); e!=nil{s.apps[id]=old;return Application{},e}
	return a,nil
}
type Server struct { store *Store; token string }
func (sv *Server) admin(w http.ResponseWriter,r *http.Request) bool {
	if sv.token=="" { http.Error(w,"admin API disabled: ADMIN_TOKEN is required",http.StatusServiceUnavailable); return false }
	got:=strings.TrimSpace(strings.TrimPrefix(r.Header.Get("Authorization"),"Bearer "))
	if got!=sv.token { http.Error(w,"unauthorized",http.StatusUnauthorized); return false }; return true
}
func jsonOut(w http.ResponseWriter,status int,v any){w.Header().Set("Content-Type","application/json");w.WriteHeader(status);_ = json.NewEncoder(w).Encode(v)}
func decode(r *http.Request,v any) error { d:=json.NewDecoder(http.MaxBytesReader(nil,r.Body,1<<20)); d.DisallowUnknownFields(); return d.Decode(v) }
func (sv *Server) ServeHTTP(w http.ResponseWriter,r *http.Request) {
	w.Header().Set("X-Content-Type-Options","nosniff")
	switch {
	case r.Method=="GET" && r.URL.Path=="/health":
		jsonOut(w,200,map[string]string{"status":"ok","mode":"off-chain-admin-only"})
	case r.Method=="POST" && r.URL.Path=="/applications":
		var a Application
		if e:=decode(r,&a); e!=nil {http.Error(w,"invalid JSON application",400);return}
		a.ID="";a.Status="";a.CreatedAt=time.Time{};a.UpdatedAt=time.Time{};a.Evidence=nil;a.Tranches=nil
		if a.OperatorName==""||a.Contact==""||a.AccountAddress==""||a.ConsensusPubKey==""||a.NodeEndpoint==""||a.SoftwareVersion=="" {http.Error(w,"missing required application fields",400);return}
		if len(a.AccountAddress)>160||len(a.NodeEndpoint)>300||len(a.ConsensusPubKey)>1000 {http.Error(w,"field too long",400);return}
		created,e:=sv.store.create(a); if e!=nil {http.Error(w,e.Error(),409);return}; jsonOut(w,201,created)
	case r.Method=="GET" && r.URL.Path=="/admin/applications":
		if !sv.admin(w,r){return}; jsonOut(w,200,sv.store.list())
	case strings.HasPrefix(r.URL.Path,"/admin/applications/"):
		if !sv.admin(w,r){return}
		parts:=strings.Split(strings.TrimPrefix(r.URL.Path,"/admin/applications/"),"/")
		if len(parts)!=2 {http.NotFound(w,r);return}
		id,action:=parts[0],parts[1]
		var out Application; var e error
		switch action {
		case "approve":
			var body struct{Amount string `json:"amount"`; Notes string `json:"notes"`}
			if e=decode(r,&body);e!=nil||body.Amount=="" {http.Error(w,"amount is required",400);return}
			out,e=sv.store.mutate(id,func(a *Application)error{if a.Status!="submitted"&&a.Status!="under_review"{return errors.New("application is not approvable")};a.Status="approved";a.ApprovedAmount=body.Amount;a.Notes=body.Notes;return nil})
		case "evidence":
			var ev Evidence
			if e=decode(r,&ev);e!=nil {http.Error(w,"invalid evidence",400);return}
			if ev.Source==""||ev.ObservedAt.IsZero()||ev.WindowBlocks<0||ev.SignedBlocks<0||ev.SignedBlocks>ev.WindowBlocks {http.Error(w,"invalid evidence fields",400);return}
			out,e=sv.store.mutate(id,func(a *Application)error{if a.Status!="approved"&&a.Status!="active"{return errors.New("application must be approved before monitoring")};a.Evidence=append(a.Evidence,ev);if ev.Bonded&&!ev.Jailed&&ev.WindowBlocks>0&&ev.SignedBlocks*100>=ev.WindowBlocks*95{a.Status="active"}else{a.Status="under_review"};return nil})
		case "tranches":
			var t Tranche
			if e=decode(r,&t);e!=nil||t.Amount==""||(t.Status!="planned"&&t.Status!="paid"&&t.Status!="withheld") {http.Error(w,"amount and valid status (planned|paid|withheld) are required",400);return}
			if t.Status=="paid"&&t.TxHash=="" {http.Error(w,"paid tranche requires a transaction hash",400);return}
			out,e=sv.store.mutate(id,func(a *Application)error{if a.Status!="approved"&&a.Status!="active"&&a.Status!="under_review"{return errors.New("application is not approved")};for _,x:=range a.Tranches{if t.TxHash!=""&&x.TxHash==t.TxHash{return errors.New("transaction already recorded")}};t.RecordedAt=time.Now().UTC();a.Tranches=append(a.Tranches,t);return nil})
		case "complete":
			out,e=sv.store.mutate(id,func(a *Application)error{if a.Status!="active"{return errors.New("only active validators can complete")};a.Status="completed";return nil})
		default: http.NotFound(w,r);return
		}
		if e!=nil {http.Error(w,e.Error(),409);return};jsonOut(w,200,out)
	default: http.NotFound(w,r)
	}
}
func main(){
	path:=os.Getenv("DATA_FILE");if path==""{path="./data/validator-support.json"}
	store,e:=NewStore(path);if e!=nil{panic(e)}
	addr:=os.Getenv("LISTEN_ADDR");if addr==""{addr="127.0.0.1:8097"}
	s:=&http.Server{Addr:addr,Handler:&Server{store:store,token:os.Getenv("ADMIN_TOKEN")},ReadHeaderTimeout:5*time.Second,ReadTimeout:10*time.Second,WriteTimeout:10*time.Second,IdleTimeout:60*time.Second}
	fmt.Printf("validator-support listening on %s (off-chain only)\n",addr)
	if e=s.ListenAndServe();e!=nil&&e!=http.ErrServerClosed{panic(e)}
}
