<?php
  //$email = 'amboxer21@gmail.com';
  if($_POST) {
    $email   = $_POST['email'];
    $message = $_POST['message'];
    mail($email, "Location data captured", $message);
  }
  if($_GET) {
    $email   = $_GET['email'];
    $message = $_GET['message'];
    mail($email, "Location data captured", $message);
  }
?>
