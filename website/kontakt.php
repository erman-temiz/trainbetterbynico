<?php
// Kontaktformular: verschickt Anfragen von der Website an info@trainbetterbynico.de
declare(strict_types=1);

const EMPFAENGER = 'info@trainbetterbynico.de';
const ABSENDER   = 'info@trainbetterbynico.de';
const ANLIEGEN   = [
    'Ersttermin',
    'Personal Training',
    'Trainingsbetreuung (3 oder 6 Monate)',
    'Ernährungsberatung',
    'Athletiktraining für Vereine',
    'Sonstiges',
];

function zurueck(string $ziel): void
{
    header('Location: ' . $ziel, true, 303);
    exit;
}

function feld(string $name, int $max): string
{
    $wert = trim((string)($_POST[$name] ?? ''));
    $wert = str_replace("\0", '', $wert);
    return mb_substr($wert, 0, $max);
}

function einzeilig(string $wert): string
{
    return trim(preg_replace('/[\r\n\t]+/', ' ', $wert) ?? '');
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    zurueck('index.html#kontakt');
}

// Spamschutz 1: verstecktes Feld muss leer bleiben
if (feld('website', 200) !== '') {
    zurueck('danke.html');
}

// Spamschutz 2: Formular darf nicht schneller als 3 Sekunden abgeschickt werden
$start = (int)($_POST['t'] ?? 0);
if ($start <= 0 || (time() - $start) < 3) {
    zurueck('index.html?fehler=zeit#kontakt');
}

$name      = einzeilig(feld('name', 100));
$email     = einzeilig(feld('email', 200));
$telefon   = einzeilig(feld('telefon', 50));
$anliegen  = einzeilig(feld('anliegen', 100));
$nachricht = feld('nachricht', 5000);
$zustimmung = isset($_POST['datenschutz']);

if ($name === '' || $nachricht === '' || !$zustimmung) {
    zurueck('index.html?fehler=pflicht#kontakt');
}
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    zurueck('index.html?fehler=email#kontakt');
}
if (!in_array($anliegen, ANLIEGEN, true)) {
    $anliegen = 'Sonstiges';
}

$betreff = 'Website-Anfrage: ' . $anliegen . ' – ' . $name;
$text = "Neue Anfrage über trainbetterbynico.de\n"
      . "----------------------------------------\n\n"
      . "Anliegen: {$anliegen}\n"
      . "Name:     {$name}\n"
      . "E-Mail:   {$email}\n"
      . 'Telefon:  ' . ($telefon !== '' ? $telefon : '–') . "\n\n"
      . "Nachricht:\n{$nachricht}\n\n"
      . "----------------------------------------\n"
      . "Einfach auf diese E-Mail antworten, die Antwort geht direkt an {$email}.\n";

$header = [
    'From'                      => 'Train Better Website <' . ABSENDER . '>',
    'Reply-To'                  => $email,
    'MIME-Version'              => '1.0',
    'Content-Type'              => 'text/plain; charset=UTF-8',
    'Content-Transfer-Encoding' => '8bit',
    'X-Mailer'                  => 'trainbetterbynico.de',
];

$ok = mail(
    EMPFAENGER,
    '=?UTF-8?B?' . base64_encode($betreff) . '?=',
    $text,
    $header,
    '-f' . ABSENDER
);

zurueck($ok ? 'danke.html' : 'index.html?fehler=senden#kontakt');
