package main

import (
	"bytes"
	"encoding/json"
\t"math/big"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"
)

func testServer(t *testing.T) *Server {
	t.Helper()
	s, err := NewStore(filepath.Join(t.TempDir(), "state.json"))
	if err != nil { t.Fatal(err) }
	budget, _ := new(big.Int).SetString("1000000000000000000000000000000", 10)
\treturn &Server{store: s, token: "test-secret", budget: budget}
}

func request(s *Server, method, path, body string, admin bool) *httptest.ResponseRecorder {
	r := httptest.NewRequest(method, path, bytes.NewBufferString(body))
	if admin { r.Header.Set("Authorization", "Bearer test-secret") }
	w := httptest.NewRecorder()
	s.ServeHTTP(w, r)
	return w
}

func createApplication(t *testing.T, s *Server, account string) Application {
	t.Helper()
	a, err := s.store.create(Application{OperatorName: "Node", Contact: "ops@example.test", AccountAddress: account, ConsensusPubKey: "pub", NodeEndpoint: "node.example:26656", SoftwareVersion: "v0.1.0"})
	if err != nil { t.Fatal(err) }
	return a
}

func TestCreateAndDuplicateApplication(t *testing.T) {
	s := testServer(t)
	body := `{"operator_name":"Node A","contact":"ops@example.test","account_address":"sobya1abc","consensus_pubkey":"pub","node_endpoint":"node.example:26656","software_version":"v0.1.0"}`
	if w := request(s, "POST", "/applications", body, false); w.Code != 201 { t.Fatalf("create: %d %s", w.Code, w.Body) }
	if w := request(s, "POST", "/applications", body, false); w.Code != 409 { t.Fatalf("duplicate: %d", w.Code) }
	if w := request(s, "POST", "/applications", body+` {}`, false); w.Code != 400 { t.Fatalf("multiple JSON values: %d", w.Code) }
}

func TestApprovalRejectsInvalidAmounts(t *testing.T) {
	s := testServer(t)
	a := createApplication(t, s, "sobya1approval")
	for _, amount := range []string{"", "0", "-1", "1.2", "1e9", " 10"} {
		body, _ := json.Marshal(map[string]string{"amount": amount})
		if w := request(s, "POST", "/admin/applications/"+a.ID+"/approve", string(body), true); w.Code != 400 {
			t.Fatalf("amount %q accepted: %d", amount, w.Code)
		}
	}
	if w := request(s, "POST", "/admin/applications/"+a.ID+"/approve", `{"amount":"1000000000000000000"}`, true); w.Code != 200 {
		t.Fatalf("valid approval: %d %s", w.Code, w.Body)
	}
}

func TestApprovalEvidenceAndCappedTranches(t *testing.T) {
	s := testServer(t)
	a := createApplication(t, s, "sobya1tranches")
	path := "/admin/applications/" + a.ID
	if w := request(s, "POST", path+"/approve", `{"amount":"1000"}`, true); w.Code != 200 { t.Fatalf("approve: %d %s", w.Code, w.Body) }
	ev := Evidence{ObservedAt: time.Now().UTC(), Source: "manual read-only RPC snapshot", Height: 10, SignedBlocks: 96, WindowBlocks: 100, Bonded: true}
	b, _ := json.Marshal(ev)
	if w := request(s, "POST", path+"/evidence", string(b), true); w.Code != 200 { t.Fatalf("evidence: %d %s", w.Code, w.Body) }
	tr := `{"amount":"600","tx_hash":"ABC123","status":"paid"}`
	if w := request(s, "POST", path+"/tranches", tr, true); w.Code != 200 { t.Fatalf("first tranche: %d %s", w.Code, w.Body) }
	if w := request(s, "POST", path+"/tranches", tr, true); w.Code != 409 { t.Fatalf("duplicate tx: %d", w.Code) }
	if w := request(s, "POST", path+"/tranches", `{"amount":"401","status":"planned"}`, true); w.Code != 409 { t.Fatalf("over grant cap: %d", w.Code) }
	if w := request(s, "POST", path+"/tranches", `{"amount":"400","status":"planned"}`, true); w.Code != 200 { t.Fatalf("within cap: %d", w.Code) }
}

func TestProgramWideBudgetCap(t *testing.T) {
	s := testServer(t)
	a1 := createApplication(t, s, "sobya1budget1")
	a2 := createApplication(t, s, "sobya1budget2")
	s.budget = big.NewInt(1000)
	if _, err := s.store.approveGrant(a1.ID, "700", "", s.budget); err != nil { t.Fatal(err) }
	if _, err := s.store.approveGrant(a2.ID, "301", "", s.budget); err == nil { t.Fatal("program-wide budget overrun was approved") }
	if _, err := s.store.approveGrant(a2.ID, "300", "", s.budget); err != nil { t.Fatalf("grant at budget cap rejected: %v", err) }
	used, err := s.store.budgetUsed()
	if err != nil || used.String() != "1000" { t.Fatalf("wrong budget accounting: %v %v", used, err) }
}

func TestAdminAuthAndNoRPCWriteSurface(t *testing.T) {
	s := testServer(t)
	for _, header := range []string{"", "test-secret", "BearerX test-secret", "Bearer  test-secret", "Bearer wrong"} {
		r := httptest.NewRequest("GET", "/admin/applications", nil)
		r.Header.Set("Authorization", header)
		w := httptest.NewRecorder()
		s.ServeHTTP(w, r)
		if w.Code != 401 { t.Fatalf("authorization %q unexpectedly accepted: %d", header, w.Code) }
	}
	if w := request(s, "POST", "/broadcast", "{}", true); w.Code != 404 { t.Fatalf("unexpected broadcast route: %d", w.Code) }
	if w := request(s, "GET", "/admin/applications", "", false); w.Code != 401 { t.Fatalf("unauthenticated admin: %d", w.Code) }
}

func TestEvidenceRejectsInvalidAndOverflowSafeRatio(t *testing.T) {
	s := testServer(t)
	a := createApplication(t, s, "sobya1evidence")
	path := "/admin/applications/" + a.ID
	if w := request(s, "POST", path+"/approve", `{"amount":"10"}`, true); w.Code != 200 { t.Fatal(w.Code) }
	ev := Evidence{ObservedAt: time.Now().UTC(), Source: "test", SignedBlocks: 1, WindowBlocks: 0, Bonded: true}
	b, _ := json.Marshal(ev)
	if w := request(s, "POST", path+"/evidence", string(b), true); w.Code != 400 { t.Fatalf("zero window accepted: %d", w.Code) }
	ev = Evidence{ObservedAt: time.Now().UTC(), Source: "test", SignedBlocks: int64(^uint64(0) >> 1), WindowBlocks: int64(^uint64(0) >> 1), Bonded: true}
	b, _ = json.Marshal(ev)
	if w := request(s, "POST", path+"/evidence", string(b), true); w.Code != 200 { t.Fatalf("large ratio overflowed: %d %s", w.Code, w.Body) }
}

func TestPersistence(t *testing.T) {
	p := filepath.Join(t.TempDir(), "state.json")
	s, err := NewStore(p)
	if err != nil { t.Fatal(err) }
	if _, err = s.create(Application{OperatorName: "Persist", Contact: "x", AccountAddress: "sobya1persist", ConsensusPubKey: "p", NodeEndpoint: "n", SoftwareVersion: "v"}); err != nil { t.Fatal(err) }
	s2, err := NewStore(p)
	if err != nil { t.Fatal(err) }
	if len(s2.list()) != 1 { t.Fatal("application was not persisted") }
}
